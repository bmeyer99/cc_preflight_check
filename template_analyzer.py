#!/usr/bin/env python3
"""
CloudFormation Template Analyzer.

This module provides functionality for analyzing CloudFormation templates
to determine the IAM permissions required for deployment. It parses templates,
evaluates conditions, and collects the required IAM actions and resource ARNs.
"""

import sys
from typing import Dict, List, Set, Tuple, Any, Optional

from resource_map import RESOURCE_ACTION_MAP
from cfn_yaml_handler import _load_template
from condition_evaluator import evaluate_condition
from resource_processor import (
    resolve_resource_name,
    construct_resource_arn,
    handle_pass_role
)
from cc_preflight_exceptions import TemplateError, ValidationError, ResourceError


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
        TemplateError: If template cannot be read or parsed
        ValidationError: If template is missing required sections
        ResourceError: If there are issues with resource processing
    """
    print(f"\nParsing template: {template_path}...")
    actions_to_simulate: Set[str] = set()
    resource_arns_for_simulation: Set[str] = set()
    prerequisite_checks: List[Dict[str, Any]] = []

    try:
        template = _load_template(template_path)
    except (TemplateError, ValidationError) as e:
        print(f"Error: {e}", file=sys.stderr)
        raise

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
        if not resource_type:
            print(f"  Warning: Resource {logical_id} is missing a Type definition, skipping", file=sys.stderr)
            continue
            
        properties = resource_def.get("Properties", {})
        
        # Check if resource has a Condition and evaluate it
        if "Condition" in resource_def:
            condition_name = resource_def["Condition"]
            print(f"  Resource {logical_id} has condition: {condition_name}")
            
            # Evaluate the condition
            try:
                condition_result = evaluate_condition(condition_name, context)
                
                # Skip resource if condition evaluates to false
                if not condition_result:
                    print(f"  Skipping resource {logical_id} due to condition {condition_name} evaluating to false")
                    continue
            except Exception as e:
                print(f"  Warning: Error evaluating condition '{condition_name}' for resource '{logical_id}': {e}. Assuming false.", file=sys.stderr)
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