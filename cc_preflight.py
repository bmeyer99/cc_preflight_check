#!/usr/bin/env python3
"""
CloudFormation Pre-flight Check Tool.

This module provides functionality to analyze CloudFormation templates
and simulate the IAM permissions required for deployment. It parses CloudFormation
templates, extracts required IAM actions based on resource types and properties,
constructs resource ARNs, and uses the AWS IAM policy simulator to verify if the
deploying principal has sufficient permissions.

Key features:
- CloudFormation template parsing with YAML tag handling
- Resource-to-IAM action mapping
- Resource name and ARN resolution
- Condition evaluation for conditional resources
- IAM permission simulation
- Prerequisite resource checking
"""

import argparse
import json
import sys
import functools
from typing import Dict, List, Set, Tuple, Any, Optional, Callable
import yaml
import boto3
from botocore.exceptions import ClientError, NoCredentialsError, PartialCredentialsError

from resource_map import RESOURCE_ACTION_MAP
from value_resolver import resolve_value

# Define CloudFormation YAML tag handlers
def cfn_ref_constructor(loader, node):
    """
    Handle !Ref tags in CloudFormation templates.
    
    Converts YAML !Ref syntax to the equivalent {"Ref": value} dictionary format
    that CloudFormation uses internally.
    
    Args:
        loader: YAML loader instance
        node: YAML node representing the !Ref tag
        
    Returns:
        Dictionary with "Ref" key and appropriate value
    """
    return {"Ref": loader.construct_scalar(node)}

def cfn_getatt_constructor(loader, node):
    """
    Handle !GetAtt tags in CloudFormation templates.
    
    Supports both string format (!GetAtt Resource.Attribute) and
    sequence format (!GetAtt [Resource, Attribute]).
    
    Args:
        loader: YAML loader instance
        node: YAML node representing the !GetAtt tag
        
    Returns:
        Dictionary with "Fn::GetAtt" key and appropriate value list
    """
    if isinstance(node, yaml.ScalarNode):
        value = loader.construct_scalar(node)
        # Split on dot for the Resource.Attribute format
        return {"Fn::GetAtt": value.split('.')}
    elif isinstance(node, yaml.SequenceNode):
        value = loader.construct_sequence(node)
        return {"Fn::GetAtt": value}
    return {"Fn::GetAtt": ["", ""]}  # Fallback for unexpected formats

def cfn_sub_constructor(loader, node):
    """
    Handle !Sub tags in CloudFormation templates.
    
    Supports both string format and array format with variable map.
    
    Args:
        loader: YAML loader instance
        node: YAML node representing the !Sub tag
        
    Returns:
        Dictionary with "Fn::Sub" key and appropriate value
    """
    if isinstance(node, yaml.ScalarNode):
        return {"Fn::Sub": loader.construct_scalar(node)}
    elif isinstance(node, yaml.SequenceNode):
        return {"Fn::Sub": loader.construct_sequence(node)}
    return {"Fn::Sub": ""}  # Fallback for unexpected formats

def cfn_join_constructor(loader, node):
    """
    Handle !Join tags in CloudFormation templates.
    
    Args:
        loader: YAML loader instance
        node: YAML node representing the !Join tag
        
    Returns:
        Dictionary with "Fn::Join" key and appropriate value list
    """
    if isinstance(node, yaml.SequenceNode):
        return {"Fn::Join": loader.construct_sequence(node)}
    return {"Fn::Join": ["", []]}  # Fallback for unexpected formats

def cfn_base_constructor(tag_name):
    """
    Create a constructor for CloudFormation intrinsic functions.
    
    This is a factory function that creates constructors for various
    CloudFormation intrinsic functions like !Select, !Split, etc.
    
    Args:
        tag_name: The name of the intrinsic function (without "Fn::" prefix)
        
    Returns:
        A constructor function that handles the specific tag
    """
    def constructor(loader, node):
        if isinstance(node, yaml.ScalarNode):
            return {f"Fn::{tag_name}": loader.construct_scalar(node)}
        elif isinstance(node, yaml.SequenceNode):
            return {f"Fn::{tag_name}": loader.construct_sequence(node)}
        elif isinstance(node, yaml.MappingNode):
            return {f"Fn::{tag_name}": loader.construct_mapping(node)}
        return {f"Fn::{tag_name}": None}  # Fallback for unexpected formats
    return constructor

# Register CloudFormation YAML tag handlers
yaml.SafeLoader.add_constructor('!Ref', cfn_ref_constructor)
yaml.SafeLoader.add_constructor('!GetAtt', cfn_getatt_constructor)
yaml.SafeLoader.add_constructor('!Sub', cfn_sub_constructor)
yaml.SafeLoader.add_constructor('!Join', cfn_join_constructor)
yaml.SafeLoader.add_constructor('!Select', cfn_base_constructor('Select'))
yaml.SafeLoader.add_constructor('!Split', cfn_base_constructor('Split'))
yaml.SafeLoader.add_constructor('!FindInMap', cfn_base_constructor('FindInMap'))
yaml.SafeLoader.add_constructor('!If', cfn_base_constructor('If'))
yaml.SafeLoader.add_constructor('!Equals', cfn_base_constructor('Equals'))
yaml.SafeLoader.add_constructor('!And', cfn_base_constructor('And'))
yaml.SafeLoader.add_constructor('!Or', cfn_base_constructor('Or'))
yaml.SafeLoader.add_constructor('!Not', cfn_base_constructor('Not'))
yaml.SafeLoader.add_constructor('!Base64', cfn_base_constructor('Base64'))
yaml.SafeLoader.add_constructor('!Cidr', cfn_base_constructor('Cidr'))
yaml.SafeLoader.add_constructor('!ImportValue', cfn_base_constructor('ImportValue'))

# Try to register with CSafeLoader if available
try:
    yaml.CSafeLoader.add_constructor('!Ref', cfn_ref_constructor)
    yaml.CSafeLoader.add_constructor('!GetAtt', cfn_getatt_constructor)
    yaml.CSafeLoader.add_constructor('!Sub', cfn_sub_constructor)
    yaml.CSafeLoader.add_constructor('!Join', cfn_join_constructor)
    yaml.CSafeLoader.add_constructor('!Select', cfn_base_constructor('Select'))
    yaml.CSafeLoader.add_constructor('!Split', cfn_base_constructor('Split'))
    yaml.CSafeLoader.add_constructor('!FindInMap', cfn_base_constructor('FindInMap'))
    yaml.CSafeLoader.add_constructor('!If', cfn_base_constructor('If'))
    yaml.CSafeLoader.add_constructor('!Equals', cfn_base_constructor('Equals'))
    yaml.CSafeLoader.add_constructor('!And', cfn_base_constructor('And'))
    yaml.CSafeLoader.add_constructor('!Or', cfn_base_constructor('Or'))
    yaml.CSafeLoader.add_constructor('!Not', cfn_base_constructor('Not'))
    yaml.CSafeLoader.add_constructor('!Base64', cfn_base_constructor('Base64'))
    yaml.CSafeLoader.add_constructor('!Cidr', cfn_base_constructor('Cidr'))
    yaml.CSafeLoader.add_constructor('!ImportValue', cfn_base_constructor('ImportValue'))
except AttributeError:
    pass  # CSafeLoader not available


# Constants for resource name properties by resource type
RESOURCE_NAME_PROPERTIES = {
    "AWS::IAM::Role": "RoleName",
    "AWS::S3::Bucket": "BucketName",
    "AWS::SQS::Queue": "QueueName",
    "AWS::SNS::Topic": "TopicName",
    "AWS::CloudTrail::Trail": "TrailName",
    "AWS::Lambda::Function": "FunctionName"
}
# This mapping is used to extract the actual resource name from the resource properties
# when constructing ARNs. For example, for an IAM role, we need the RoleName property.


def get_aws_account_id(sts_client) -> str:
    """
    Get current AWS Account ID.
    
    Args:
        sts_client: AWS STS client
        
    Returns:
        AWS account ID
        
    Raises:
        SystemExit: If account ID cannot be determined
    """
    try:
        return sts_client.get_caller_identity()["Account"]
    except (ClientError, NoCredentialsError, PartialCredentialsError) as e:
        print(f"Error: Could not determine AWS Account ID. {e}", file=sys.stderr)
        sys.exit(1)

def evaluate_condition(condition_name: str, context: Dict[str, Any]) -> bool:
    """
    Evaluate a CloudFormation condition based on input values or the template's Conditions block.
    
    This function handles condition evaluation for CloudFormation templates, supporting:
    1. Direct condition values provided as input
    2. Fn::Equals condition expressions
    3. References to other conditions
    
    Other condition functions (Fn::And, Fn::Or, Fn::Not, Fn::If) are recognized but
    not fully implemented yet, and will default to False with a warning.
    
    Args:
        condition_name: The name of the condition to evaluate
        context: Dictionary containing template data, resolved parameters, and condition values
                 Must include: "template", "parameters", "account_id", "region"
                 May include: "condition_values", "evaluated_conditions"
        
    Returns:
        Boolean result of the condition evaluation
    """
    # Check if we've already evaluated this condition (memoization)
    if "evaluated_conditions" not in context:
        context["evaluated_conditions"] = {}
    
    if condition_name in context["evaluated_conditions"]:
        return context["evaluated_conditions"][condition_name]
    
    # First check if the condition is directly provided in input values
    if "condition_values" in context and condition_name in context["condition_values"]:
        result = context["condition_values"][condition_name]
        context["evaluated_conditions"][condition_name] = result
        return result
    
    # If not in input values, check if it's defined in the template
    if "Conditions" in context["template"] and condition_name in context["template"]["Conditions"]:
        condition_def = context["template"]["Conditions"][condition_name]
        
        # Handle different intrinsic functions in conditions
        if isinstance(condition_def, dict):
            if "Fn::Equals" in condition_def:
                # Evaluate Fn::Equals
                equals_args = condition_def["Fn::Equals"]
                if len(equals_args) == 2:
                    resources = context["template"].get("Resources", {})
                    left_value = resolve_value(equals_args[0], context["parameters"],
                                              context["account_id"], context["region"],
                                              resources)
                    right_value = resolve_value(equals_args[1], context["parameters"],
                                               context["account_id"], context["region"],
                                               resources)
                    result = (left_value == right_value)
                    context["evaluated_conditions"][condition_name] = result
                    return result
            
            # Handle condition reference
            elif "Condition" in condition_def:
                # Reference to another condition
                referenced_condition = condition_def["Condition"]
                result = evaluate_condition(referenced_condition, context)
                context["evaluated_conditions"][condition_name] = result
                return result
                
            # Handle other condition functions (not fully implemented yet)
            elif "Fn::And" in condition_def:
                print(f"Warning: Fn::And condition not fully supported yet. Defaulting to False for {condition_name}",
                      file=sys.stderr)
                context["evaluated_conditions"][condition_name] = False
                return False
            elif "Fn::Or" in condition_def:
                print(f"Warning: Fn::Or condition not fully supported yet. Defaulting to False for {condition_name}",
                      file=sys.stderr)
                context["evaluated_conditions"][condition_name] = False
                return False
            elif "Fn::Not" in condition_def:
                print(f"Warning: Fn::Not condition not fully supported yet. Defaulting to False for {condition_name}",
                      file=sys.stderr)
                context["evaluated_conditions"][condition_name] = False
                return False
            elif "Fn::If" in condition_def:
                print(f"Warning: Fn::If condition not fully supported yet. Defaulting to False for {condition_name}",
                      file=sys.stderr)
                context["evaluated_conditions"][condition_name] = False
                return False
    
    # If we get here, the condition wasn't found
    print(f"Error: Condition '{condition_name}' not found in input values or template.", file=sys.stderr)
    context["evaluated_conditions"][condition_name] = False
    return False


# Cache for resource name resolution
@functools.lru_cache(maxsize=128)
def _cached_resolve_resource_name(resource_type: str, logical_id: str,
                                 name_prop_key: Optional[str], prop_value_str: str,
                                 resolve_func: Callable) -> str:
    """
    Cached version of resolve_resource_name.
    
    This function serves as a memoization wrapper around the resource name resolution
    process. It caches results based on the input parameters to avoid redundant
    resolution of the same resource names, which improves performance when
    processing large templates with many references to the same resources.
    
    Args:
        resource_type: The CloudFormation resource type
        logical_id: The logical ID of the resource
        name_prop_key: The property key for the resource name
        prop_value_str: String representation of the property value
        resolve_func: Function to call for actual resolution
        
    Returns:
        Resolved resource name
    """
    return resolve_func()

def resolve_resource_name(resource_type: str, logical_id: str, properties: Dict[str, Any],
                         resolved_cfn_parameters: Dict[str, Any], account_id: str,
                         region: str, resources: Dict[str, Any]) -> str:
    """
    Resolve the resource name from properties or generate a default name.
    
    This function extracts the actual resource name (e.g., BucketName for S3 buckets)
    from the resource properties. If the name property is not specified or the
    resource type is not recognized, it falls back to using the logical ID with
    a wildcard suffix.
    
    The function uses the RESOURCE_NAME_PROPERTIES mapping to determine which
    property contains the resource name for each resource type.
    
    Args:
        resource_type: The CloudFormation resource type (e.g., "AWS::S3::Bucket")
        logical_id: The logical ID of the resource in the template
        properties: The resource properties dictionary
        resolved_cfn_parameters: Resolved CloudFormation parameters
        account_id: AWS account ID for ARN construction
        region: AWS region for ARN construction
        resources: Dictionary of resources in the template
        
    Returns:
        Resolved resource name or default pattern (logical_id-*)
    """
    # Get the appropriate property name for this resource type
    name_prop_key = RESOURCE_NAME_PROPERTIES.get(resource_type)
    
    # Define the resolution function
    def resolve_func():
        # Default to wildcard
        if not name_prop_key or name_prop_key not in properties:
            # Use logical ID as fallback
            return f"{logical_id}-*"
        
        # Resolve the name from the property
        return resolve_value(
            properties[name_prop_key],
            resolved_cfn_parameters,
            account_id,
            region,
            resources
        )
    
    # Use caching for repeated resolutions
    prop_value_str = str(properties.get(name_prop_key, "")) if name_prop_key else ""
    return _cached_resolve_resource_name(
        resource_type,
        logical_id,
        name_prop_key,
        prop_value_str,
        resolve_func
    )


# Cache for ARN construction
@functools.lru_cache(maxsize=128)
def _cached_construct_resource_arn(resource_type: str, logical_id: str, resource_name: str,
                                  arn_pattern: str, account_id: str, region: str) -> str:
    """
    Cached version of construct_resource_arn.
    
    This function serves as a memoization wrapper around the ARN construction
    process. It caches results based on the input parameters to avoid redundant
    construction of the same ARNs, which improves performance when processing
    large templates with many references to the same resources.
    
    Args:
        resource_type: The CloudFormation resource type
        logical_id: The logical ID of the resource
        resource_name: The resolved resource name
        arn_pattern: The ARN pattern from the resource map
        account_id: AWS account ID
        region: AWS region
        
    Returns:
        Constructed ARN for the resource
    """
    # Special handling for S3 buckets without names
    if resource_type == "AWS::S3::Bucket" and "{bucketNamePlaceholder}" in arn_pattern:
        if not resource_name or resource_name == "*":
            resource_name = ""
            arn_pattern = "arn:aws:s3:::{bucketNamePlaceholder}-*"
    
    # Replace placeholders in ARN pattern - optimize by doing direct string replacements
    # rather than iterating through a dictionary
    current_arn = arn_pattern
    current_arn = current_arn.replace("{accountId}", str(account_id) if account_id is not None else "*")
    current_arn = current_arn.replace("{region}", str(region) if region is not None else "*")
    current_arn = current_arn.replace("{resourceLogicalIdPlaceholder}", logical_id)
    
    # Resource-specific placeholders
    resource_name_str = str(resource_name)
    current_arn = current_arn.replace("{roleName}", resource_name_str)
    current_arn = current_arn.replace("{policyName}", resource_name_str)
    current_arn = current_arn.replace("{functionName}", resource_name_str)
    current_arn = current_arn.replace("{bucketName}", resource_name_str)
    current_arn = current_arn.replace("{queueName}", resource_name_str)
    current_arn = current_arn.replace("{topicName}", resource_name_str)
    current_arn = current_arn.replace("{trailName}", resource_name_str)
    current_arn = current_arn.replace("{aliasName}", resource_name_str)
    current_arn = current_arn.replace("{stackSetName}", resource_name_str)
    
    # Special handling for S3 bucket placeholder
    if resource_type == "AWS::S3::Bucket" and "{bucketNamePlaceholder}" in current_arn:
        current_arn = current_arn.replace("{bucketNamePlaceholder}", f"cfn-{logical_id.lower()}")
    
    return current_arn

def construct_resource_arn(resource_type: str, logical_id: str, resource_name: str,
                          arn_pattern: str, account_id: str, region: str) -> str:
    """
    Construct a resource ARN for simulation.
    
    This function builds an AWS ARN (Amazon Resource Name) for a given resource
    by replacing placeholders in the ARN pattern with actual values. The ARN
    is used for IAM policy simulation to determine if the deploying principal
    has the necessary permissions.
    
    Special handling is provided for certain resource types like S3 buckets.
    
    Args:
        resource_type: The CloudFormation resource type (e.g., "AWS::S3::Bucket")
        logical_id: The logical ID of the resource in the template
        resource_name: The resolved resource name
        arn_pattern: The ARN pattern from the resource map
        account_id: AWS account ID for ARN construction
        region: AWS region for ARN construction
        
    Returns:
        Constructed ARN for the resource
    """
    return _cached_construct_resource_arn(
        resource_type, logical_id, resource_name, arn_pattern, account_id, region
    )


def handle_pass_role(properties: Dict[str, Any], prop_key: str, prop_actions: List[str],
                    resolved_cfn_parameters: Dict[str, Any], account_id: str,
                    region: str, resources: Dict[str, Any]) -> Optional[str]:
    """
    Handle PassRole permissions for resources that need them.
    
    Many AWS services require IAM roles to be passed to them during resource creation.
    This function identifies when a resource property requires the iam:PassRole
    permission and resolves the ARN of the role that needs to be passed.
    
    Args:
        properties: Resource properties dictionary
        prop_key: The property key (e.g., "Role")
        prop_actions: Actions associated with the property
        resolved_cfn_parameters: Resolved CloudFormation parameters
        account_id: AWS account ID for ARN construction
        region: AWS region for ARN construction
        resources: Dictionary of resources in the template
        
    Returns:
        The ARN to pass role to, or None if not applicable
    """
    if prop_key == "Role" and "iam:PassRole" in prop_actions:
        role_arn_to_pass = resolve_value(
            properties[prop_key],
            resolved_cfn_parameters,
            account_id,
            region,
            resources
        )
        
        if isinstance(role_arn_to_pass, str) and role_arn_to_pass.startswith("arn:"):
            return role_arn_to_pass
        else:
            # Create a placeholder ARN
            return f"arn:aws:iam::{account_id}:role/{role_arn_to_pass}-*"
    
    return None

# Cache for template loading
@functools.lru_cache(maxsize=8)
def _load_template(template_path: str) -> Dict[str, Any]:
    """
    Load and parse a CloudFormation template with caching.
    
    This function loads a CloudFormation template from a file and parses it
    into a Python dictionary. It uses caching to avoid reloading the same
    template multiple times, which is useful for performance optimization.
    
    The function attempts to use the C-based YAML loader (CSafeLoader) for
    better performance, falling back to the Python-based loader if necessary.
    
    Args:
        template_path: Path to the CloudFormation template file
        
    Returns:
        Parsed template as a dictionary
        
    Raises:
        Exception: If template cannot be read or parsed
    """
    with open(template_path, 'r') as f:
        # Use C-based YAML loader if available for better performance
        try:
            # Try to use the C-based loader for better performance
            return yaml.CSafeLoader(f).get_data()
        except AttributeError:
            # Fall back to the Python-based loader
            return yaml.safe_load(f)

def parse_template_and_collect_actions(template_path: str, cfn_parameters: Dict[str, Any],
                                      account_id: str, region: str,
                                      condition_values: Optional[Dict[str, bool]] = None) -> Tuple[List[str], List[str], List[Dict[str, Any]]]:
    """
    Parse the CloudFormation template and collect IAM actions and resource ARNs required for deployment.
    
    This is the core function of the pre-flight check tool. It:
    1. Loads and parses the CloudFormation template
    2. Resolves template parameters
    3. Evaluates conditions to determine which resources to process
    4. For each resource, determines the required IAM actions based on resource type and properties
    5. Constructs ARNs for each resource for IAM policy simulation
    6. Identifies any prerequisite resources that need to exist before deployment
    
    Args:
        template_path: Path to the CloudFormation template file
        cfn_parameters: Dictionary of parameter names to their values
        account_id: AWS account ID for ARN construction
        region: AWS region for ARN construction
        condition_values: Optional dictionary of condition names to boolean values
        
    Returns:
        Tuple containing:
        - List of IAM actions to simulate
        - List of resource ARNs for simulation
        - List of prerequisite checks to perform
        
    Raises:
        SystemExit: If template cannot be read or parsed
    """
    print(f"\nParsing template: {template_path}...")
    actions_to_simulate: Set[str] = set()
    resource_arns_for_simulation: Set[str] = set()
    prerequisite_checks: List[Dict[str, Any]] = []

    try:
        template = _load_template(template_path)
    except Exception as e:
        print(f"Error: Could not read or parse template file '{template_path}'. {e}", file=sys.stderr)
        sys.exit(1)

    template_parameters = template.get("Parameters", {})
    resources = template.get("Resources", {})
    
    # Create context for condition evaluation
    context = {
        "template": template,
        "parameters": {},  # Will be populated with resolved parameters
        "account_id": account_id,
        "region": region,
        "condition_values": condition_values or {}
    }
    
    # Resolve parameters (use provided values or defaults)
    resolved_cfn_parameters = {}
    for param_key, param_def in template_parameters.items():
        if param_key in cfn_parameters:
            resolved_cfn_parameters[param_key] = cfn_parameters[param_key]
        elif "Default" in param_def:
            resolved_cfn_parameters[param_key] = param_def["Default"]
    
    # Update context with resolved parameters
    context["parameters"] = resolved_cfn_parameters

    # Check for required prerequisite parameters
    if "OutpostRoleArn" in resolved_cfn_parameters:
        prerequisite_checks.append({
            "type": "iam_role_exists",
            "arn": resolved_cfn_parameters["OutpostRoleArn"],
            "description": "OutpostRoleArn parameter"
        })

    print(f"Resolved CloudFormation Parameters for pre-flight checks: {resolved_cfn_parameters}")

    # Process each resource in the template
    for logical_id, resource_def in resources.items():
        resource_type = resource_def.get("Type")
        properties = resource_def.get("Properties", {})
        
        # Check if resource has a Condition and evaluate it
        if "Condition" in resource_def:
            condition_name = resource_def["Condition"]
            print(f"  Resource {logical_id} has condition: {condition_name}")
            
            # Evaluate the condition
            condition_result = evaluate_condition(condition_name, context)
            
            # Skip resource if condition evaluates to false
            if not condition_result:
                print(f"  Skipping resource {logical_id} due to condition {condition_name} evaluating to false")
                continue

        print(f"  Processing resource: {logical_id} (Type: {resource_type})")

        if resource_type in RESOURCE_ACTION_MAP:
            map_entry = RESOURCE_ACTION_MAP[resource_type]

            # Handle custom resources
            if map_entry.get("type") == "CustomResource":
                print(f"    Info: Custom Resource. Primary permissions are tied to its handler (Lambda).")
                actions_to_simulate.add("cloudformation:CreateStack")
                continue

            # 1. Add generic actions for the resource type - optimize by using a set update
            generic_actions = map_entry.get("generic_actions", [])
            if generic_actions:
                actions_to_simulate.update(generic_actions)

            # 2. Get ARN pattern for this resource type
            arn_pattern_str = map_entry.get("arn_pattern", "arn:aws:*:{region}:{accountId}:{resourceLogicalIdPlaceholder}/*")
            
            # 3. Resolve resource name from properties
            resource_name = resolve_resource_name(
                resource_type,
                logical_id,
                properties,
                resolved_cfn_parameters,
                account_id,
                region,
                resources
            )
            
            # 4. Construct the ARN for simulation
            current_arn = construct_resource_arn(
                resource_type,
                logical_id,
                resource_name,
                arn_pattern_str,
                account_id,
                region
            )
            
            resource_arns_for_simulation.add(current_arn)

            # 5. Check properties for specific actions - optimize property lookup
            property_actions_map = map_entry.get("property_actions", {})
            if property_actions_map:
                # Only iterate through properties that exist in the property_actions_map
                for prop_key in set(properties.keys()).intersection(property_actions_map.keys()):
                    prop_actions = property_actions_map[prop_key]
                    actions_to_simulate.update(prop_actions)
                    
                    # Handle PassRole permissions
                    pass_role_arn = handle_pass_role(
                        properties,
                        prop_key,
                        prop_actions,
                        resolved_cfn_parameters,
                        account_id,
                        region,
                        resources
                    )
                    
                    if pass_role_arn:
                        resource_arns_for_simulation.add(pass_role_arn)
                        print(f"    Info: Added potential PassRole ARN for simulation: {pass_role_arn}")
            
            # 6. Handle Tags - common across many resources
            if "Tags" in properties and resource_type.count("::") >= 2:
                service_prefix = resource_type.split("::")[1].lower()
                tag_action = f"{service_prefix}:TagResource"
                create_tags_action = f"{service_prefix}:CreateTags"
                
                # Optimize tag action check
                generic_actions_set = set(map_entry.get("generic_actions", []))
                has_tag_action = (
                    tag_action in actions_to_simulate or
                    create_tags_action in actions_to_simulate or
                    any(action.endswith("Tagging") or action.startswith(f"{service_prefix}:Tag")
                        for action in generic_actions_set)
                )
                
                if not has_tag_action:
                    actions_to_simulate.add(tag_action)
                    print(f"    Info: Added generic '{tag_action}' for Tags.")
        else:
            # Unknown resource type
            print(f"    Warning: No specific IAM action mapping found for resource type: {resource_type}.",
                  file=sys.stderr)
            actions_to_simulate.add("cloudformation:CreateStack")

    return sorted(list(actions_to_simulate)), sorted(list(resource_arns_for_simulation)), prerequisite_checks


def check_prerequisites(checks: List[Dict[str, Any]], iam_client, region: str) -> bool:
    """
    Check for existence and basic configuration of prerequisite resources.
    
    Some CloudFormation templates require certain resources to exist before
    deployment, such as IAM roles referenced by ARN. This function verifies
    that these prerequisite resources exist and are properly configured.
    
    Currently supports checking for:
    - IAM role existence
    
    Args:
        checks: List of prerequisite checks to perform
        iam_client: AWS IAM client
        region: AWS region
        
    Returns:
        Boolean indicating if all prerequisite checks passed
    """
    print("\n--- Checking Prerequisites ---")
    all_prereqs_ok = True
    
    for check in checks:
        print(f"  Checking: {check['description']} (ARN: {check['arn']})")
        
        if check["type"] == "iam_role_exists":
            try:
                # Extract role name from ARN
                role_name = check["arn"].split('/')[-1]
                iam_client.get_role(RoleName=role_name)
                print(f"    [PASS] Prerequisite IAM Role '{check['arn']}' exists.")
            except ClientError as e:
                if e.response['Error']['Code'] == 'NoSuchEntity':
                    print(f"    [FAIL] Prerequisite IAM Role '{check['arn']}' does not exist.")
                    all_prereqs_ok = False
                else:
                    print(f"    [ERROR] Error checking prerequisite IAM Role: {e}")
                    all_prereqs_ok = False
            except Exception as e:
                print(f"    [ERROR] Unexpected error checking prerequisite: {e}")
                all_prereqs_ok = False

    # Summary
    if not checks:
        print("  No specific prerequisite resource checks defined.")
    elif all_prereqs_ok:
        print("  All checked prerequisites appear to be in place.")
    else:
        print("  Some prerequisite checks failed.")
        
    return all_prereqs_ok


def simulate_iam_permissions(iam_client, principal_arn: str, actions: List[str],
                            resource_arns: List[str],
                            context_entries: Optional[List[Dict[str, Any]]] = None) -> Tuple[bool, List[Dict[str, Any]]]:
    """
    Simulate IAM permissions for the given principal, actions, and resources.
    
    This function uses the AWS IAM Policy Simulator API to check if the specified
    principal (user, role, or group) has the necessary permissions to perform
    the required actions on the specified resources. This allows for pre-flight
    validation of permissions without actually attempting the operations.
    
    The function handles:
    - Preparing the simulation input
    - Running the simulation via the IAM API
    - Processing and displaying the results
    - Identifying specific reasons for permission denials (e.g., SCPs, permission boundaries)
    
    Args:
        iam_client: AWS IAM client
        principal_arn: ARN of the principal to simulate permissions for
        actions: List of IAM actions to simulate
        resource_arns: List of resource ARNs to simulate against
        context_entries: Optional list of context entries for the simulation
                        (e.g., for condition keys like aws:RequestTag)
        
    Returns:
        Tuple containing:
        - Boolean indicating if all actions are allowed
        - List of failed simulation results
    """
    print("\n--- Simulating IAM Permissions ---")
    print(f"  Principal ARN for Simulation: {principal_arn}")
    print(f"  Actions to Simulate ({len(actions)}): {actions}")
    print(f"  Resource ARNs for Simulation ({len(resource_arns)}): {resource_arns if resource_arns else ['*']}")

    # Skip simulation if no actions to simulate
    if not actions:
        print("  No actions to simulate. Skipping IAM simulation.")
        return True, []
    
    try:
        # Prepare simulation input
        simulation_input = {
            'PolicySourceArn': principal_arn,
            'ActionNames': actions,
            'ResourceArns': resource_arns if resource_arns else ['*']
        }
        
        if context_entries:
            simulation_input['ContextEntries'] = context_entries
        
        # Run simulation
        response = iam_client.simulate_principal_policy(**simulation_input)
        
        all_allowed = True
        failed_simulations = []

        # Process results
        print("\n  Simulation Results:")
        for eval_result in response.get('EvaluationResults', []):
            eval_action_name = eval_result['EvalActionName']
            eval_decision = eval_result['EvalDecision']
            eval_resource_name = eval_result.get('EvalResourceName', '*')

            # Display result
            decision_marker = "[PASS]" if eval_decision == "allowed" else "[FAIL]"
            print(f"    {decision_marker} Action: {eval_action_name}, Resource: {eval_resource_name}")

            # Track failures
            if eval_decision != "allowed":
                all_allowed = False
                failed_simulations.append(eval_result)
                
                # Show denial reasons
                if eval_result.get('OrganizationsDecisionDetail', {}).get('AllowedByOrganizations') == False:
                    print(f"      Denied by: Organizations SCP")
                if eval_result.get('PermissionsBoundaryDecisionDetail', {}).get('AllowedByPermissionsBoundary') == False:
                    print(f"      Denied by: Permissions Boundary")

        # Summary
        if all_allowed:
            print("\n  [SUCCESS] All simulated actions are allowed for the principal.")
        else:
            print("\n  [FAILURE] Some simulated actions were DENIED. Review details above.")
        
        return all_allowed, failed_simulations

    except ClientError as e:
        print(f"  [ERROR] IAM simulation failed: {e}", file=sys.stderr)
        return False, [{"error": str(e)}]
    except Exception as e:
        print(f"  [ERROR] An unexpected error occurred: {e}", file=sys.stderr)
        return False, [{"error": str(e)}]


def main() -> None:
    """
    Main entry point for the CloudFormation pre-flight check tool.
    
    This function:
    1. Parses command line arguments
    2. Initializes AWS clients (IAM, STS)
    3. Parses the CloudFormation template
    4. Collects required IAM actions and resource ARNs
    5. Checks for prerequisite resources
    6. Simulates IAM permissions
    7. Provides a summary of the results
    
    The tool exits with status code 0 if all checks pass, 1 otherwise.
    
    Command line arguments:
    --template-file: Path to the CloudFormation template
    --deploying-principal-arn: ARN of the principal deploying the template
    --region: AWS region for deployment
    --parameters: CloudFormation parameters as Key=Value pairs
    --profile: AWS CLI profile to use
    --condition-values: JSON string of condition name to boolean value mappings
    """
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Perform pre-flight checks for CloudFormation template.")
    parser.add_argument("--template-file", required=True, help="Path to the CloudFormation template.")
    parser.add_argument("--deploying-principal-arn", required=True, help="ARN of the deploying principal.")
    parser.add_argument("--region", required=True, help="AWS Region for deployment.")
    parser.add_argument("--parameters", nargs='*', help="CloudFormation parameters as Key=Value pairs.")
    parser.add_argument("--profile", help="AWS CLI profile to use.")
    parser.add_argument("--condition-values", help="JSON string of condition name to boolean value mappings.")

    args = parser.parse_args()

    try:
        session_params = {}
        if args.profile:
            session_params["profile_name"] = args.profile
        if args.region:
            session_params["region_name"] = args.region

        session = boto3.Session(**session_params)
        iam_client = session.client("iam")
        sts_client = session.client("sts")
        print(f"Using AWS region: {session.region_name or 'Default from config'}")
    except (PartialCredentialsError, NoCredentialsError) as e:
        print(f"Error: AWS credentials issue. {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error: Could not initialize AWS session. {e}", file=sys.stderr)
        sys.exit(1)

    account_id = get_aws_account_id(sts_client)

    # Parse CLI parameters
    cfn_cli_parameters = {}
    if args.parameters:
        for p_item in args.parameters:
            if "=" not in p_item:
                print(f"Error: Parameter '{p_item}' is not in Key=Value format.", file=sys.stderr)
                sys.exit(1)
            key, value = p_item.split("=", 1)
            cfn_cli_parameters[key] = value
    
    # Parse condition values if provided
    condition_values = None
    if args.condition_values:
        try:
            condition_values = json.loads(args.condition_values)
            print(f"Using provided condition values: {condition_values}")
        except json.JSONDecodeError as e:
            print(f"Error: Could not parse condition values JSON. {e}", file=sys.stderr)
            sys.exit(1)
    
    # Step 1: Parse Template & Collect Actions
    actions, resource_arns, prerequisite_checks = parse_template_and_collect_actions(
        args.template_file, cfn_cli_parameters, account_id, args.region, condition_values
    )

    # Step 2: Check Prerequisites
    prereqs_ok = check_prerequisites(prerequisite_checks, iam_client, args.region)

    # Step 3: Simulate IAM Permissions
    context_entries = []
    if "ExternalID" in cfn_cli_parameters:
        context_entries.append({
            "ContextKeyName": "sts:ExternalId",
            "ContextKeyValues": [cfn_cli_parameters["ExternalID"]],
            "ContextKeyType": "string"
        })

    permissions_ok, failed_sims = simulate_iam_permissions(
        iam_client, args.deploying_principal_arn, actions, resource_arns, context_entries
    )

    # Final Summary
    print("\n--- Pre-flight Check Summary ---")
    if prereqs_ok:
        print("[PASS] Prerequisite checks passed or no prerequisites to check.")
    else:
        print("[FAIL] Some prerequisite checks failed.")

    if permissions_ok:
        print("[PASS] IAM permission simulation indicates all permissions are present.")
    else:
        print("[FAIL] IAM permission simulation indicates missing permissions.")
        print("        Review the simulation details above for denied actions.")

    if prereqs_ok and permissions_ok:
        print("\nPre-flight checks completed successfully.")
        sys.exit(0)
    else:
        print("\nPre-flight checks identified issues. Review failures before deploying.")
        sys.exit(1)


if __name__ == "__main__":
    main()