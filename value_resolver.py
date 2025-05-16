#!/usr/bin/env python3
"""
CloudFormation value resolver module.

This module provides functionality to resolve CloudFormation intrinsic functions
and references to their simplified values for pre-flight checks. It handles the
resolution of CloudFormation's intrinsic functions (Ref, Fn::Sub, Fn::GetAtt, Fn::Join)
and provides a caching mechanism to improve performance.

The module is designed to work with the cc_preflight.py tool to analyze CloudFormation
templates and determine the required IAM permissions for deployment. It resolves
references to parameters, pseudo-parameters, and resources to construct accurate
resource ARNs for IAM policy simulation.
"""

import sys
import re
import functools
from typing import Any, Dict, List, Optional, Union, Tuple, Callable

# Default values for CloudFormation pseudo parameters
PSEUDO_PARAMETER_RESOLUTIONS = {
    "AWS::Partition": "aws",
    "AWS::Region": "us-east-1",
    "AWS::AccountId": "123456789012",
    "AWS::StackName": "my-test-stack",
    "AWS::StackId": "arn:aws:cloudformation:us-east-1:123456789012:stack/my-test-stack/abcdefgh-1234-ijkl-5678-mnopqrstuvwx",
    "AWS::URLSuffix": "amazonaws.com",
    "AWS::NoValue": None
}

# Type aliases for better readability
Parameters = Dict[str, Any]
Resources = Dict[str, Dict[str, Any]]
CFValue = Union[Dict[str, Any], List[Any], str, int, bool, None]


def resolve_ref(ref_val: str, parameters: Parameters, account_id: str,
                resources_in_template: Resources) -> Any:
    """
    Resolve CloudFormation Ref function.
    
    This function handles the resolution of CloudFormation's Ref intrinsic function.
    It resolves references in the following order of precedence:
    1. CloudFormation pseudo-parameters (AWS::Region, AWS::AccountId, etc.)
    2. Template parameters (with provided values or defaults)
    3. Resources defined in the template (returns a placeholder ARN)
    
    If the reference cannot be resolved, a warning is printed and a placeholder
    is returned.
    
    Args:
        ref_val: The reference value to resolve (e.g., "MyParameter", "AWS::Region")
        parameters: Dictionary of parameter names to their values
        account_id: AWS account ID for ARN construction
        resources_in_template: Dictionary of resource logical IDs to their definitions
        
    Returns:
        The resolved reference value, which could be a string, number, boolean,
        or None (for AWS::NoValue)
    """
    # 1. Check for Pseudo Parameters
    if ref_val in PSEUDO_PARAMETER_RESOLUTIONS:
        return PSEUDO_PARAMETER_RESOLUTIONS[ref_val]
    
    # 2. Check for Parameters
    if ref_val in parameters:
        # Parameter reference - return the resolved parameter value (includes defaults)
        return parameters[ref_val]
    
    # 3. Check for Resources
    if ref_val in resources_in_template:
        # Resource reference - return a placeholder ARN
        return f"arn:aws:::resolved-ref-{ref_val.lower()}"
    
    # 4. Unresolved Ref - neither a pseudo-param, parameter nor a resource in the template
    print(f"Warning: Unresolved Ref: {ref_val}", file=sys.stderr)
    return f"UNRESOLVED_REF_FOR_{ref_val}"


def resolve_sub(sub_val: Any, parameters: Parameters, account_id: str,
                region: str, resources_in_template: Resources) -> str:
    """
    Resolve CloudFormation Fn::Sub function.
    
    This function handles the resolution of CloudFormation's Fn::Sub intrinsic function,
    which substitutes variables in a string with their corresponding values.
    
    Currently, this implementation primarily supports the string form of Fn::Sub.
    The list form with explicit variable mappings is recognized but not fully supported.
    
    Variables in the string are identified by ${VarName} syntax and are resolved
    in the following order:
    1. CloudFormation pseudo-parameters (AWS::Region, AWS::AccountId, etc.)
    2. Template parameters (with provided values or defaults)
    3. Resources defined in the template (returns a placeholder ARN)
    
    The function also handles literal dollar signs ($$) by replacing them with a
    single dollar sign ($) according to CloudFormation behavior.
    
    Args:
        sub_val: The Sub value to resolve (string or list form)
        parameters: Dictionary of parameter names to their values
        account_id: AWS account ID for ARN construction
        region: AWS region for ARN construction
        resources_in_template: Dictionary of resource logical IDs to their definitions
        
    Returns:
        The resolved string after substitution
    """
    # Only handle string form of Fn::Sub
    if not isinstance(sub_val, str):
        print(f"Warning: Fn::Sub list form or complex expressions not fully supported for pre-flight resolution: {sub_val}",
              file=sys.stderr)
        return str(sub_val)
    
    # Handle simple string substitution
    def replace_sub_variables(match):
        variable_name = match.group(1)
        
        # 1. Check for Pseudo Parameters
        if variable_name in PSEUDO_PARAMETER_RESOLUTIONS:
            value = PSEUDO_PARAMETER_RESOLUTIONS[variable_name]
            return "" if value is None else str(value)  # Handle None for NoValue
        
        # 2. Check for Parameters
        if variable_name in parameters:
            return str(parameters[variable_name])
        
        # 3. Check for Logical Resource IDs
        if variable_name in resources_in_template:
            # Return a placeholder for resource logical IDs
            return f"arn:aws:::resolved-sub-{variable_name.lower()}"
        
        # 4. Unresolved - return a placeholder
        print(f"Warning: Unresolved variable in Fn::Sub: ${{{variable_name}}}", file=sys.stderr)
        return f"UNRESOLVED_SUB_VAR_{variable_name}"

    # Use the replacement function to handle variable substitutions
    resolved_sub = re.sub(r"\$\{(.+?)\}", replace_sub_variables, sub_val)
    
    # Handle literal dollar signs (replace $$ with $) according to CloudFormation behavior
    resolved_sub = resolved_sub.replace("$$", "$")
    
    return resolved_sub


def resolve_get_att(get_att_val: List[str], parameters: Parameters, account_id: str,
                   region: str, resources_in_template: Resources) -> str:
    """
    Resolve CloudFormation Fn::GetAtt function.
    
    This function handles the resolution of CloudFormation's Fn::GetAtt intrinsic function,
    which retrieves the value of an attribute from a resource in the template.
    
    The implementation provides special handling for common resource types and attributes,
    returning appropriate placeholder values based on the resource type and attribute.
    For example, for an IAM role's ARN, it returns a properly formatted IAM role ARN
    with the account ID.
    
    For unsupported resource types or attributes, a generic placeholder is returned.
    
    Args:
        get_att_val: The GetAtt value to resolve [logical_id, attribute]
        parameters: Dictionary of parameter names to their values
        account_id: AWS account ID for ARN construction
        region: AWS region for ARN construction
        resources_in_template: Dictionary of resource logical IDs to their definitions
        
    Returns:
        The resolved attribute value as a string
    """
    logical_id = get_att_val[0]
    attribute = get_att_val[1]
    
    # Check if the resource exists in the template
    if logical_id in resources_in_template:
        resource_type = resources_in_template[logical_id].get("Type", "")
        
        # Handle different resource types with appropriate ARN formats
        if resource_type == "AWS::IAM::Role" and attribute == "Arn":
            return f"arn:aws:iam::{account_id}:role/resolved-getatt-{logical_id.lower()}-{attribute.lower()}"
        
        elif resource_type == "AWS::S3::Bucket":
            if attribute == "DomainName":
                return f"resolved-getatt-{logical_id.lower()}-{attribute.lower()}.s3.amazonaws.com"
            elif attribute == "Arn":
                return f"arn:aws:s3:::resolved-getatt-{logical_id.lower()}-{attribute.lower()}"
        
        elif resource_type == "AWS::Lambda::Function" and attribute == "Arn":
            return f"arn:aws:lambda:{region}:{account_id}:function:resolved-getatt-{logical_id.lower()}-{attribute.lower()}"
        
        elif resource_type == "AWS::SQS::Queue":
            if attribute == "QueueUrl":
                return f"https://sqs.{region}.amazonaws.com/{account_id}/resolved-getatt-{logical_id.lower()}-{attribute.lower()}"
            elif attribute == "Arn":
                return f"arn:aws:sqs:{region}:{account_id}:resolved-getatt-{logical_id.lower()}-{attribute.lower()}"
        
        elif resource_type == "AWS::SNS::Topic" and attribute == "TopicArn":
            return f"arn:aws:sns:{region}:{account_id}:resolved-getatt-{logical_id.lower()}-{attribute.lower()}"
        
        elif resource_type == "AWS::KMS::Key" and attribute == "KeyId":
            return f"resolved-getatt-{logical_id.lower()}-{attribute.lower()}"
        
        elif resource_type == "AWS::CloudTrail::Trail" and attribute == "Arn":
            return f"arn:aws:cloudtrail:{region}:{account_id}:trail/resolved-getatt-{logical_id.lower()}-{attribute.lower()}"
    
    # For unsupported resource types or attributes, return a generic placeholder
    print(f"Warning: Specific GetAtt resolution not available for {logical_id}.{attribute}. Using generic placeholder.",
          file=sys.stderr)
    return f"getatt:{logical_id}.{attribute}"


def resolve_join(join_val: List[Any], parameters: Parameters, account_id: str,
                region: str, resources_in_template: Resources) -> str:
    """
    Resolve CloudFormation Fn::Join function.
    
    This function handles the resolution of CloudFormation's Fn::Join intrinsic function,
    which joins a list of values with a specified delimiter.
    
    The function:
    1. Extracts the delimiter and list of items to join
    2. Resolves each item in the list (which may contain nested intrinsic functions)
    3. Joins the resolved items with the delimiter
    
    Special handling is provided for None values (from AWS::NoValue), which are
    converted to empty strings before joining.
    
    Args:
        join_val: The Join value to resolve [delimiter, [items]]
        parameters: Dictionary of parameter names to their values
        account_id: AWS account ID for ARN construction
        region: AWS region for ARN construction
        resources_in_template: Dictionary of resource logical IDs to their definitions
        
    Returns:
        The resolved joined string
    """
    delimiter = join_val[0]
    list_to_join = join_val[1]
    
    # Resolve each item in the list, handling None values from AWS::NoValue
    resolved_list = []
    for item in list_to_join:
        resolved_item = resolve_value(item, parameters, account_id, region, resources_in_template)
        resolved_list.append("" if resolved_item is None else str(resolved_item))
    
    return delimiter.join(resolved_list)


# Create a cache key function for memoization
def _make_cache_key(value: CFValue, parameters: Parameters, account_id: str,
                   region: str, resources_in_template: Resources) -> Tuple:
    """
    Create a hashable cache key for memoization of resolve_value.
    
    This function generates a unique, hashable key for caching the results of
    resolve_value calls. Since Python's lru_cache requires hashable arguments,
    this function converts potentially unhashable inputs (like dictionaries and lists)
    into hashable tuples.
    
    The cache key includes:
    - The identity of the resources dictionary (to avoid cross-template contamination)
    - The value being resolved (converted to a hashable representation)
    - The account ID and region (which affect ARN construction)
    
    Parameters are not included in the key because they're accessed by reference
    and their identity is sufficient for caching purposes.
    
    Args:
        value: The value to resolve (could be a string, number, dict, list, etc.)
        parameters: Dictionary of parameter names to their values
        account_id: AWS account ID for ARN construction
        region: AWS region for ARN construction
        resources_in_template: Dictionary of resource logical IDs to their definitions
        
    Returns:
        A hashable tuple that can be used as a cache key
    """
    # For primitive types, use the value directly
    if value is None or isinstance(value, (str, int, float, bool)):
        return (id(resources_in_template), value, account_id, region)
    
    # For dictionaries, create a hashable representation
    if isinstance(value, dict):
        # Sort items to ensure consistent key regardless of dict order
        items = tuple(sorted((k, str(v)) for k, v in value.items()))
        return (id(resources_in_template), "dict", items, account_id, region)
    
    # For lists, create a hashable representation
    if isinstance(value, list):
        # Convert list items to strings for hashability
        items = tuple(str(item) for item in value)
        return (id(resources_in_template), "list", items, account_id, region)
    
    # Fallback for other types
    return (id(resources_in_template), str(value), account_id, region)

# Use LRU cache for memoization
@functools.lru_cache(maxsize=1024)
def _resolve_value_cached(cache_key: Tuple, value_str: str,
                         resolve_func: Callable) -> Any:
    """
    Cached version of resolve_value that works with the cache key.
    
    This function serves as a memoization wrapper around the value resolution
    process. It caches results based on the cache key to avoid redundant
    resolution of the same values, which significantly improves performance
    when processing large templates with many repeated references.
    
    The cache_key parameter is not used directly in the function but is
    included as a parameter to enable caching based on its value.
    
    Args:
        cache_key: The cache key (not used directly, just for caching)
        value_str: String representation of the value (for debugging)
        resolve_func: Function to call for actual resolution
        
    Returns:
        The resolved value
    """
    return resolve_func()

def resolve_value(value: CFValue, parameters: Parameters, account_id: str,
                 region: str, resources_in_template: Resources) -> Any:
    """
    Resolve CloudFormation intrinsic functions and references to their simplified values.
    
    This is the main entry point for resolving CloudFormation values. It handles:
    - Primitive values (strings, numbers, booleans, None)
    - Intrinsic functions (Ref, Fn::Sub, Fn::GetAtt, Fn::Join)
    - Nested structures (dictionaries and lists)
    
    The function uses memoization via _resolve_value_cached to improve performance
    when processing large templates with repeated references.
    
    Fast paths are provided for primitive values to avoid the overhead of caching
    when it's not needed.
    
    Args:
        value: The value to resolve, which may contain intrinsic functions
        parameters: Dictionary of parameter names to their values
        account_id: AWS account ID for ARN construction
        region: AWS region for ARN construction
        resources_in_template: Dictionary of resource logical IDs to their definitions
        
    Returns:
        The resolved value after processing any intrinsic functions
    """
    # Fast path for None values
    if value is None:
        return None
    
    # Fast path for primitive values
    if isinstance(value, (str, int, float, bool)):
        return value
    
    # For more complex values, use memoization
    def resolve_func():
        # Handle dictionaries (potential intrinsic functions)
        if isinstance(value, dict):
            # Handle intrinsic functions
            if "Ref" in value:
                return resolve_ref(value["Ref"], parameters, account_id, resources_in_template)
            
            elif "Fn::Sub" in value:
                return resolve_sub(value["Fn::Sub"], parameters, account_id, region, resources_in_template)
            
            elif "Fn::GetAtt" in value:
                return resolve_get_att(value["Fn::GetAtt"], parameters, account_id, region, resources_in_template)
            
            elif "Fn::Join" in value:
                return resolve_join(value["Fn::Join"], parameters, account_id, region, resources_in_template)
            
            # Recurse for nested structures
            return {k: resolve_value(v, parameters, account_id, region, resources_in_template)
                    for k, v in value.items()}
        
        # Handle lists
        elif isinstance(value, list):
            return [resolve_value(item, parameters, account_id, region, resources_in_template)
                    for item in value]
        
        # Return primitive values as-is (should be handled by fast path)
        return value
    
    # Create a cache key and use the cached version
    cache_key = _make_cache_key(value, parameters, account_id, region, resources_in_template)
    return _resolve_value_cached(cache_key, str(value), resolve_func)