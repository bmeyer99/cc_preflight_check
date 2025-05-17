#!/usr/bin/env python3
"""
CloudFormation Resource Processor.

This module provides functionality for processing CloudFormation resources,
including resolving resource names, constructing ARNs, and handling special
cases like IAM PassRole permissions.
"""

import functools
from typing import Dict, List, Any, Optional, Callable

from value_resolver import resolve_value


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