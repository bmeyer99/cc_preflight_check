#!/usr/bin/env python3

# PSEUDO_PARAMETER_RESOLUTIONS moved from cc_preflight.py
PSEUDO_PARAMETER_RESOLUTIONS = {
    "AWS::Partition": "aws",  # Or could be "PSEUDO_PARAM_AWS::Partition"
    "AWS::Region": "us-east-1",  # Or a configurable default
    "AWS::AccountId": "123456789012",  # Or a configurable default
    "AWS::StackName": "my-test-stack",  # Or a configurable default
    "AWS::StackId": "arn:aws:cloudformation:us-east-1:123456789012:stack/my-test-stack/abcdefgh-1234-ijkl-5678-mnopqrstuvwx",  # Or a placeholder
    "AWS::URLSuffix": "amazonaws.com",
    "AWS::NoValue": None  # Should resolve to None
}

def resolve_value(value, parameters, account_id, region, resources_in_template):
    """
    Resolve CloudFormation intrinsic functions and references to their simplified values.
    
    Args:
        value: The value to resolve, which may contain intrinsic functions
        parameters: Dictionary of parameter names to their values
        account_id: AWS account ID for ARN construction
        region: AWS region for ARN construction
        resources_in_template: Dictionary of resource logical IDs to their definitions
        
    Returns:
        The resolved value after processing any intrinsic functions
    """
    if isinstance(value, dict):
        if "Ref" in value:
            ref_val = value["Ref"]
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
                # Using a consistent placeholder format
                return f"arn:aws:::resolved-ref-{ref_val.lower()}"
            # 4. Unresolved Ref - neither a pseudo-param, parameter nor a resource in the template
            print(f"Warning: Unresolved Ref: {ref_val}", file=sys.stderr)
            return f"UNRESOLVED_REF_FOR_{ref_val}"
        elif "Fn::Sub" in value:
            sub_val = value["Fn::Sub"]
            # Extremely simplified Sub - only handles direct replacements of global/params
            # Does not handle the list form of Fn::Sub or complex expressions.
            if isinstance(sub_val, str):
                # Handle simple string substitution
                def replace_sub_variables(match):
                    variable_name = match.group(1)
                    # 1. Check for Pseudo Parameters
                    if variable_name in PSEUDO_PARAMETER_RESOLUTIONS:
                         return str(PSEUDO_PARAMETER_RESOLUTIONS[variable_name]) if PSEUDO_PARAMETER_RESOLUTIONS[variable_name] is not None else "" # Handle None for NoValue
                    # 2. Check for Parameters
                    if variable_name in parameters:
                        return str(parameters[variable_name])
                    # 3. Check for Logical Resource IDs
                    if variable_name in resources_in_template:
                        # Return a placeholder for resource logical IDs
                        return f"arn:aws:::resolved-sub-{variable_name.lower()}" # This might need refinement depending on resource type
                    # 4. Unresolved - return a placeholder
                    print(f"Warning: Unresolved variable in Fn::Sub: ${{{variable_name}}}", file=sys.stderr)
                    return f"UNRESOLVED_SUB_VAR_{variable_name}"

                # Use the updated replacement function
                resolved_sub = re.sub(r"\$\{(.+?)\}", replace_sub_variables, sub_val)
                return resolved_sub
            else: # List form of Fn::Sub not fully supported here
                print(f"Warning: Fn::Sub list form or complex expressions not fully supported for pre-flight resolution: {sub_val}", file=sys.stderr)
                return str(value)
        elif "Fn::GetAtt" in value:
             # Pre-flight resolution of GetAtt is hard. Return a placeholder or logical ID.
            print(f"Warning: Fn::GetAtt resolution not supported in pre-flight: {value}", file=sys.stderr)
            return f"getatt:{value['Fn::GetAtt'][0]}.{value['Fn::GetAtt'][1]}"
        elif "Fn::Join" in value:
            delimiter = value["Fn::Join"][0]
            list_to_join = value["Fn::Join"][1]
            # Ensure resolution handles None from AWS::NoValue correctly in join
            resolved_list = [str(resolve_value(item, parameters, account_id, region, resources_in_template)) if resolve_value(item, parameters, account_id, region, resources_in_template) is not None else "" for item in list_to_join]
            return delimiter.join(resolved_list)

        # Recurse for nested structures
        return {k: resolve_value(v, parameters, account_id, region, resources_in_template) for k, v in value.items()}
    elif isinstance(value, list):
        # Ensure resolution handles None from AWS::NoValue correctly in lists
        return [resolve_value(item, parameters, account_id, region, resources_in_template) for item in value]
    # Handle AWS::NoValue resolving to None
    if value is None:
        return None
    return value

# Required imports
import sys
import re