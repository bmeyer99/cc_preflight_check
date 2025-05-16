#!/usr/bin/env python3
import argparse
import json
import sys
import yaml
import boto3
import re
from botocore.exceptions import ClientError, NoCredentialsError, PartialCredentialsError

# --- IAM Action Mapping (Extend this for more coverage) ---
# This is a crucial part. It maps CloudFormation resource types to:
# - A list of IAM actions generally required for creation/management.
# - A function to derive a resource ARN pattern for simulation (can be tricky for non-existent resources).
# - A function to extract specific permissions based on resource properties.
# Placeholders like '{accountId}', '{region}', '{resourceName}' will be substituted.
# Using '*' for resource names in ARNs is common for pre-flight checks on non-existent resources.

RESOURCE_ACTION_MAP = {
    "AWS::IAM::Role": {
        "generic_actions": [
            "iam:CreateRole",
            "iam:DeleteRole",
            "iam:TagRole",
            "iam:UntagRole"
        ],
        "arn_pattern": "arn:aws:iam::{accountId}:role/{roleName}",
        "property_actions": {
            "ManagedPolicyArns": ["iam:AttachRolePolicy", "iam:DetachRolePolicy"],
            "Policies": ["iam:PutRolePolicy", "iam:DeleteRolePolicy"],
            "PermissionsBoundary": ["iam:PutRolePermissionsBoundary", "iam:DeleteRolePermissionsBoundary"],
            "AssumeRolePolicyDocument": []
        },
        "operation_actions": {
            "Create": ["iam:CreateRole", "iam:PutRolePolicy", "iam:AttachRolePolicy", "iam:TagRole"],
            "Update": ["iam:PutRolePolicy", "iam:AttachRolePolicy", "iam:DetachRolePolicy", "iam:TagRole", "iam:UntagRole"],
            "Delete": ["iam:DeleteRole", "iam:DeleteRolePolicy", "iam:DetachRolePolicy"],
            "Tag": ["iam:TagRole", "iam:UntagRole"]
        },
        "pass_role_to_services": []
    },
    "AWS::IAM::Policy": {
        "generic_actions": ["iam:CreatePolicy", "iam:DeletePolicy", "iam:TagPolicy"],
        "arn_pattern": "arn:aws:iam::{accountId}:policy/{policyName}",
        "property_actions": {}
    },
    "AWS::Lambda::Function": {
        "generic_actions": [
            "lambda:CreateFunction",
            "lambda:DeleteFunction",
            "lambda:TagResource",
            "lambda:UntagResource",
            "lambda:UpdateFunctionConfiguration",
            "lambda:UpdateFunctionCode"
        ],
        "arn_pattern": "arn:aws:lambda:{region}:{accountId}:function:{functionName}",
        "property_actions": {
            "Role": ["iam:PassRole"]
        },
        "operation_actions": {
            "Create": ["lambda:CreateFunction", "iam:PassRole", "lambda:TagResource"],
            "Update": ["lambda:UpdateFunctionConfiguration", "lambda:UpdateFunctionCode", "lambda:TagResource", "lambda:UntagResource"],
            "Delete": ["lambda:DeleteFunction"],
            "Tag": ["lambda:TagResource", "lambda:UntagResource"]
        },
        "#note": "Also needs permissions for event sources (e.g., SQS, SNS) if defined."
    },
    "AWS::Lambda::Permission": {
        "generic_actions": ["lambda:AddPermission", "lambda:RemovePermission"],
        "arn_pattern": "arn:aws:lambda:{region}:{accountId}:function:{functionName}",
        "property_actions": {}
    },
    "AWS::S3::Bucket": {
        "generic_actions": [
            "s3:CreateBucket",
            "s3:DeleteBucket",
            "s3:PutBucketTagging",
            "s3:DeleteBucketTagging",
            "s3:PutEncryptionConfiguration",
            "s3:PutLifecycleConfiguration",
            "s3:PutBucketPolicy",
            "s3:PutBucketVersioning",
            "s3:PutAccelerateConfiguration",
            "s3:PutBucketAcl",
            "s3:GetBucketAcl"
        ],
        "arn_pattern": "arn:aws:s3:::{bucketName}",
        "property_actions": {},
        "operation_actions": {
            "Create": ["s3:CreateBucket", "s3:PutBucketEncryption", "s3:PutLifecycleConfiguration", "s3:PutBucketTagging"],
            "Update": ["s3:PutBucketEncryption", "s3:PutLifecycleConfiguration", "s3:PutBucketTagging", "s3:DeleteBucketTagging"],
            "Delete": ["s3:DeleteBucket"],
            "Tag": ["s3:PutBucketTagging", "s3:DeleteBucketTagging"]
        }
    },
    "AWS::S3::BucketPolicy": {
        "generic_actions": ["s3:PutBucketPolicy", "s3:DeleteBucketPolicy"],
        "arn_pattern": "arn:aws:s3:::{bucketName}",
        "property_actions": {},
        "operation_actions": {
            "Create": ["s3:PutBucketPolicy"],
            "Update": ["s3:PutBucketPolicy"],
            "Delete": ["s3:DeleteBucketPolicy"],
            "Tag": []
        }
    },
    "AWS::SQS::Queue": {
        "generic_actions": ["sqs:CreateQueue", "sqs:DeleteQueue", "sqs:TagQueue", "sqs:UntagQueue", "sqs:SetQueueAttributes"],
        "arn_pattern": "arn:aws:sqs:{region}:{accountId}:{queueName}",
        "property_actions": {},
        "operation_actions": {
            "Create": ["sqs:CreateQueue", "sqs:TagQueue"],
            "Update": ["sqs:SetQueueAttributes", "sqs:TagQueue", "sqs:UntagQueue"],
            "Delete": ["sqs:DeleteQueue"],
            "Tag": ["sqs:TagQueue", "sqs:UntagQueue"]
        }
    },
    "AWS::SQS::QueuePolicy": {
        "generic_actions": ["sqs:AddPermission", "sqs:RemovePermission"],
        "arn_pattern": "arn:aws:sqs:{region}:{accountId}:{queueName}",
        "property_actions": {},
        "operation_actions": {
            "Create": ["sqs:AddPermission"],
            "Update": ["sqs:AddPermission", "sqs:RemovePermission"],
            "Delete": ["sqs:RemovePermission"],
            "Tag": []
        }
    },
    "AWS::SNS::Topic": {
        "generic_actions": ["sns:CreateTopic", "sns:DeleteTopic", "sns:TagResource", "sns:UntagResource", "sns:SetTopicAttributes"],
        "arn_pattern": "arn:aws:sns:{region}:{accountId}:{topicName}",
        "property_actions": {},
        "operation_actions": {
            "Create": ["sns:CreateTopic", "sns:TagResource"],
            "Update": ["sns:SetTopicAttributes", "sns:TagResource", "sns:UntagResource"],
            "Delete": ["sns:DeleteTopic"],
            "Tag": ["sns:TagResource", "sns:UntagResource"]
        }
    },
    "AWS::SNS::TopicPolicy": {
        "generic_actions": ["sns:AddPermission", "sns:RemovePermission", "sns:PutDataProtectionPolicy"],
        "arn_pattern": "arn:aws:sns:{region}:{accountId}:{topicName}",
        "property_actions": {},
        "operation_actions": {
            "Create": ["sns:AddPermission", "sns:PutDataProtectionPolicy"],
            "Update": ["sns:AddPermission", "sns:RemovePermission", "sns:PutDataProtectionPolicy"],
            "Delete": ["sns:RemovePermission"],
            "Tag": []
        }
    },
    "AWS::SNS::Subscription": {
        "generic_actions": ["sns:Subscribe", "sns:Unsubscribe", "sns:SetSubscriptionAttributes"],
        "arn_pattern": "arn:aws:sns:{region}:{accountId}:{topicName}:*",
        "property_actions": {
            "Endpoint": [],
            "Protocol": []
        },
        "operation_actions": {
            "Create": ["sns:Subscribe"],
            "Update": ["sns:SetSubscriptionAttributes"],
            "Delete": ["sns:Unsubscribe"],
            "Tag": []
        }
    },
    "AWS::KMS::Key": {
        "generic_actions": [
            "kms:CreateKey",
            "kms:TagResource",
            "kms:UntagResource",
            "kms:ScheduleKeyDeletion",
            "kms:PutKeyPolicy",
            "kms:UpdateKeyDescription",
            "kms:EnableKey",
            "kms:DisableKey",
            "kms:EnableKeyRotation",
            "kms:DisableKeyRotation"
        ],
        "arn_pattern": "arn:aws:kms:{region}:{accountId}:key/*",
        "property_actions": {
             "KeyPolicy": ["kms:PutKeyPolicy"],
             "Description": ["kms:UpdateKeyDescription"],
             "Enabled": ["kms:EnableKey", "kms:DisableKey"],
             "EnableKeyRotation": ["kms:EnableKeyRotation", "kms:DisableKeyRotation"]
        },
        "operation_actions": {
            "Create": ["kms:CreateKey", "kms:PutKeyPolicy", "kms:TagResource"],
            "Update": ["kms:PutKeyPolicy", "kms:UpdateKeyDescription", "kms:EnableKey", "kms:DisableKey", "kms:EnableKeyRotation", "kms:DisableKeyRotation", "kms:TagResource", "kms:UntagResource"],
            "Delete": ["kms:ScheduleKeyDeletion"],
            "Tag": ["kms:TagResource", "kms:UntagResource"]
        }
    },
    "AWS::KMS::Alias": {
        "generic_actions": ["kms:CreateAlias", "kms:DeleteAlias", "kms:UpdateAlias"],
        "arn_pattern": "arn:aws:kms:{region}:{accountId}:alias/{aliasName}",
        "property_actions": {}
    },
    "AWS::CloudTrail::Trail": {
        "generic_actions": [
            "cloudtrail:CreateTrail",
            "cloudtrail:DeleteTrail",
            "cloudtrail:UpdateTrail",
            "cloudtrail:StartLogging",
            "cloudtrail:StopLogging",
            "cloudtrail:TagResource",
            "cloudtrail:RemoveTags",
            "cloudtrail:ListTags",
            "cloudtrail:PutEventSelectors",
            "iam:CreateServiceLinkedRole",
            "iam:GetRole",
            "organizations:ListAWSServiceAccessForOrganization"
        ],
        "arn_pattern": "arn:aws:cloudtrail:{region}:{accountId}:trail/{trailName}",
        "property_actions": {
            "S3BucketName": ["s3:PutObject", "s3:GetBucketPolicy", "s3:GetBucketAcl"],
            "KMSKeyId": ["kms:DescribeKey", "kms:GenerateDataKey*", "kms:Decrypt"],
            "CloudWatchLogsLogGroupArn": ["logs:CreateLogStream", "logs:PutLogEvents", "logs:DescribeLogGroups"],
            "RoleArn": ["iam:PassRole"]
        },
        "operation_actions": {
            "Create": ["cloudtrail:CreateTrail", "cloudtrail:AddTags", "iam:CreateServiceLinkedRole", "iam:GetRole", "organizations:ListAWSServiceAccessForOrganization"],
            "Update": ["cloudtrail:UpdateTrail", "cloudtrail:PutEventSelectors", "cloudtrail:StartLogging", "cloudtrail:StopLogging", "cloudtrail:AddTags", "cloudtrail:RemoveTags"],
            "Delete": ["cloudtrail:DeleteTrail"],
            "Tag": ["cloudtrail:AddTags", "cloudtrail:RemoveTags", "cloudtrail:ListTags"]
        }
    },
    "AWS::CloudFormation::StackSet": {
        "generic_actions": [
            "cloudformation:CreateStackSet",
            "cloudformation:DeleteStackSet",
            "cloudformation:DescribeStackSet",
            "cloudformation:UpdateStackSet",
            "cloudformation:CreateStackInstances",
            "cloudformation:DeleteStackInstances",
            "cloudformation:TagResource",
            "cloudformation:UntagResource",
            "iam:PassRole"
        ],
        "arn_pattern": "arn:aws:cloudformation:{region}:{accountId}:stackset/{stackSetName}:*",
        "property_actions": {},
        "operation_actions": {
            "Create": ["cloudformation:CreateStackSet", "cloudformation:CreateStackInstances", "cloudformation:TagResource"],
            "Update": ["cloudformation:UpdateStackSet", "cloudformation:UpdateStackInstances", "cloudformation:TagResource", "cloudformation:UntagResource"],
            "Delete": ["cloudformation:DeleteStackSet", "cloudformation:DeleteStackInstances"],
            "Tag": ["cloudformation:TagResource", "cloudformation:UntagResource"]
        },
        "#note": "Permissions for StackSet instances in target accounts are complex and depend on PermissionModel."
    },
    # Custom resources are backed by Lambdas. Permissions are needed for the Lambda and its execution role.
    # The permissions for what the Lambda *does* are on its execution role.
    # The deploying principal needs to create the Lambda and its role.
    "Custom::PublishRoleDetail": {
        "type": "CustomResource",
        "operation_actions": {
            "Create": ["organizations:DescribeOrganization", "s3:PutObject"],
            "Update": ["organizations:DescribeOrganization", "s3:PutObject"],
            "Delete": [],
            "Tag": []
        }
    },
    "Custom::EmptyBucketDetails": { "type": "CustomResource" }
}

# Helper to get current AWS Account ID
def get_aws_account_id(sts_client):
    try:
        return sts_client.get_caller_identity()["Account"]
    except (ClientError, NoCredentialsError, PartialCredentialsError) as e:
        print(f"Error: Could not determine AWS Account ID. {e}", file=sys.stderr)
        sys.exit(1)

# Helper to resolve simple !Ref and !Sub
# Add simulated/placeholder values for pseudo-parameters
PSEUDO_PARAMETER_RESOLUTIONS = {
    "AWS::Partition": "aws", # Or could be "PSEUDO_PARAM_AWS::Partition"
    "AWS::Region": "us-east-1", # Or a configurable default
    "AWS::AccountId": "123456789012", # Or a configurable default
    "AWS::StackName": "my-test-stack", # Or a configurable default
    "AWS::StackId": "arn:aws:cloudformation:us-east-1:123456789012:stack/my-test-stack/abcdefgh-1234-ijkl-5678-mnopqrstuvwx", # Or a placeholder
    "AWS::URLSuffix": "amazonaws.com",
    "AWS::NoValue": None # Should resolve to None
}

# Helper to resolve simple !Ref and !Sub
:start_line:283
-------
def resolve_value(value, parameters, account_id, region, resources_in_template, context):
    """
    Recursively resolves intrinsic functions and references in a CloudFormation template value.
    Includes support for Fn::If.
    """
    if isinstance(value, dict):
        if "Fn::If" in value:
            if isinstance(value["Fn::If"], list) and len(value["Fn::If"]) == 3:
                condition_name = value["Fn::If"][0]
                value_if_true = value["Fn::If"][1]
                value_if_false = value["Fn::If"][2]
                try:
                    # Evaluate the condition using the evaluate_condition function
                    condition_result = evaluate_condition(condition_name, template, context) # template is available in this scope
                    if condition_result:
                        print(f"    Info: Fn::If condition '{condition_name}' evaluated to True. Resolving 'value_if_true'.")
                        return resolve_value(value_if_true, parameters, account_id, region, resources_in_template, context)
                    else:
                        print(f"    Info: Fn::If condition '{condition_name}' evaluated to False. Resolving 'value_if_false'.")
                        return resolve_value(value_if_false, parameters, account_id, region, resources_in_template, context)
                except ValueError as e:
                    print(f"    Warning: Error evaluating condition '{condition_name}' in Fn::If: {e}", file=sys.stderr)
                    # Return a placeholder or raise an error for unresolved conditions in Fn::If
                    return f"UNRESOLVED_CONDITION_IN_FN_IF_{condition_name}"
            else:
                print(f"    Warning: Invalid arguments for Fn::If: {value['Fn::If']}", file=sys.stderr)
                return f"INVALID_FN_IF_FORMAT_{str(value['Fn::If'])}"
        elif "Ref" in value:
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
            # Resolve Fn::GetAtt for common attributes
            getatt_params = value["Fn::GetAtt"]
            if not isinstance(getatt_params, list) or len(getatt_params) != 2:
                print(f"Warning: Invalid Fn::GetAtt format: {value}", file=sys.stderr)
                return f"INVALID_GETATT_FORMAT_{str(value)}"

            logical_resource_id = getatt_params[0]
            attribute_name = getatt_params[1]

            resource_def = resources_in_template.get(logical_resource_id)
            if not resource_def:
                print(f"Warning: Fn::GetAtt refers to unknown resource: {logical_resource_id}", file=sys.stderr)
                return f"UNKNOWN_RESOURCE_FOR_GETATT_{logical_resource_id}"

            resource_type = resource_def.get("Type")
            if not resource_type:
                print(f"Warning: Resource {logical_resource_id} has no Type defined.", file=sys.stderr)
                return f"RESOURCE_WITHOUT_TYPE_FOR_GETATT_{logical_resource_id}"

            # Use a consistent format for placeholders
            placeholder_prefix = f"resolved-getatt-{logical_resource_id.lower()}-{attribute_name.lower()}"

            # --- Implement specific attribute resolution based on resource type ---
            if resource_type == "AWS::IAM::Role":
                if attribute_name == "Arn":
                    return f"arn:aws:iam::PSEUDO_PARAM_AWS::AccountId:role/{placeholder_prefix}"
                elif attribute_name == "RoleId":
                    return f"RESOLVED_GETATT_{logical_resource_id.upper()}_ROLEID_AIDAJQABLZS4A3QDU576Q" # Example RoleId format
            elif resource_type == "AWS::S3::Bucket":
                if attribute_name == "Arn":
                    return f"arn:aws:s3:::{placeholder_prefix}"
                elif attribute_name == "DomainName":
                    return f"{placeholder_prefix}.s3.amazonaws.com"
                elif attribute_name == "DualStackDomainName":
                     return f"{placeholder_prefix}.s3.dualstack.PSEUDO_PARAM_AWS::Region.amazonaws.com"
                elif attribute_name == "RegionalDomainName":
                     return f"{placeholder_prefix}.s3.PSEUDO_PARAM_AWS::Region.amazonaws.com"
                elif attribute_name == "WebsiteURL":
                     return f"http://{placeholder_prefix}.s3-website-PSEUDO_PARAM_AWS::Region.amazonaws.com"
            elif resource_type == "AWS::Lambda::Function":
                if attribute_name == "Arn":
                    return f"arn:aws:lambda:PSEUDO_PARAM_AWS::Region:PSEUDO_PARAM_AWS::AccountId:function:{placeholder_prefix}"
                elif attribute_name == "Name":
                    return f"{placeholder_prefix}"
            elif resource_type == "AWS::SQS::Queue":
                if attribute_name == "Arn":
                    return f"arn:aws:sqs:PSEUDO_PARAM_AWS::Region:PSEUDO_PARAM_AWS::AccountId:{placeholder_prefix}"
                elif attribute_name == "QueueName":
                    return f"{placeholder_prefix}"
                elif attribute_name == "QueueUrl":
                     return f"https://sqs.PSEUDO_PARAM_AWS::Region.amazonaws.com/PSEUDO_PARAM_AWS::AccountId/{placeholder_prefix}"
            elif resource_type == "AWS::SNS::Topic":
                if attribute_name == "TopicArn":
                    return f"arn:aws:sns:PSEUDO_PARAM_AWS::Region:PSEUDO_PARAM_AWS::AccountId:{placeholder_prefix}"
                elif attribute_name == "TopicName":
                    return f"{placeholder_prefix}"
            elif resource_type == "AWS::KMS::Key":
                if attribute_name == "Arn":
                    return f"arn:aws:kms:PSEUDO_PARAM_AWS::Region:PSEUDO_PARAM_AWS::AccountId:key/{placeholder_prefix}"
                elif attribute_name == "KeyId":
                    return f"{placeholder_prefix}" # KeyId is a UUID-like string
            elif resource_type == "AWS::CloudTrail::Trail":
                if attribute_name == "Arn":
                    return f"arn:aws:cloudtrail:PSEUDO_PARAM_AWS::Region:PSEUDO_PARAM_AWS::AccountId:trail/{placeholder_prefix}"
                elif attribute_name == "SnsTopicArn":
                     # Assuming the SNS topic is also in the template or a known pattern
                     return f"arn:aws:sns:PSEUDO_PARAM_AWS::Region:PSEUDO_PARAM_AWS::AccountId:resolved-getatt-{logical_resource_id.lower()}-snstopicarn"
                elif attribute_name == "S3BucketArn":
                     # Assuming the S3 bucket is also in the template or a known pattern
                     return f"arn:aws:s3:::resolved-getatt-{logical_resource_id.lower()}-s3bucketarn"
                elif attribute_name == "S3BucketName":
                     # Assuming the S3 bucket is also in the template or a known pattern
                     return f"resolved-getatt-{logical_resource_id.lower()}-s3bucketname"

            # Handle unsupported attributes for known resource types
            print(f"Warning: Unsupported Fn::GetAtt attribute '{attribute_name}' for resource type '{resource_type}'", file=sys.stderr)
            return f"UNSUPPORTED_GETATT_ATTRIBUTE_{attribute_name}_ON_RESOURCE_TYPE_{resource_type}"

        elif "Fn::Join" in value:
            delimiter = value["Fn::Join"][0]
:start_line:433
-------
            list_to_join = value["Fn::Join"][1]
            # Ensure resolution handles None from AWS::NoValue correctly in join
            resolved_list = [str(resolve_value(item, parameters, account_id, region, resources_in_template, context)) if resolve_value(item, parameters, account_id, region, resources_in_template, context) is not None else "" for item in list_to_join]
            return delimiter.join(resolved_list)

        # Recurse for nested structures
        return {k: resolve_value(v, parameters, account_id, region, resources_in_template, context) for k, v in value.items()}
    elif isinstance(value, list):
        # Ensure resolution handles None from AWS::NoValue correctly in lists
        return [resolve_value(item, parameters, account_id, region, resources_in_template, context) for item in value]
    # Handle AWS::NoValue resolving to None
    if value is None:
        return None
    return value


def evaluate_condition(condition_name, template, context):
    """
    Evaluates a CloudFormation condition based on input values or the template's Conditions block.
    Supports Fn::Equals, Fn::And, Fn::Or, Fn::Not, and direct condition references.
    """
    # Ensure evaluated_conditions dictionary exists in context for memoization
    if 'evaluated_conditions' not in context:
        context['evaluated_conditions'] = {}

    # 1. Check if condition_name is present in the input condition values (from P2-T2.1)
    condition_input_values = context.get("condition_input_values", {})
    if condition_name in condition_input_values:
        result = condition_input_values[condition_name]
        print(f"    Info: Condition '{condition_name}' found in input values: {result}")
        context['evaluated_conditions'][condition_name] = result # Memoize
        return result

    # 2. Check if the condition has already been evaluated (memoization)
    if condition_name in context['evaluated_conditions']:
        print(f"    Info: Condition '{condition_name}' found in cache: {context['evaluated_conditions'][condition_name]}")
        return context['evaluated_conditions'][condition_name]

    # 3. Look up condition_name in the template's Conditions block
    conditions_block = template.get('Conditions', {})
    condition_definition = conditions_block.get(condition_name)

    if condition_definition is None:
        # 4. Condition not found in inputs or template
        raise ValueError(f"Condition '{condition_name}' not found in inputs or template Conditions.")

    print(f"    Evaluating condition '{condition_name}' from template...")

    # 5. Evaluate the condition definition
    result = False # Default result for unsupported functions

    if isinstance(condition_definition, dict) and len(condition_definition) == 1:
        intrinsic_function, args = list(condition_definition.items())[0]

        if intrinsic_function == "Fn::Equals":
            if isinstance(args, list) and len(args) == 2:
                value1 = resolve_value(args[0], context["parameters"], context["account_id"], context["region"], context["resources_in_template"])
                value2 = resolve_value(args[1], context["parameters"], context["account_id"], context["region"], context["resources_in_template"])
                # CloudFormation compares resolved values as strings for Fn::Equals
                result = str(value1) == str(value2)
                print(f"    Info: Evaluated Fn::Equals for '{condition_name}': {value1} == {value2} -> {result}")
            else:
                print(f"    Warning: Invalid arguments for Fn::Equals in condition '{condition_name}': {args}", file=sys.stderr)
                # Decide whether to return False or raise error for invalid format
                # Returning False for now, but raising error might be better for strict validation
:start_line:497
-------
                result = False # Treat invalid format as false
        elif intrinsic_function == "Fn::And":
            if isinstance(args, list):
                # Evaluate all conditions in the list. All must be True for Fn::And to be True.
                result = all(evaluate_condition(arg, template, context) for arg in args)
                print(f"    Info: Evaluated Fn::And for '{condition_name}': {result}")
            else:
                print(f"    Warning: Invalid arguments for Fn::And in condition '{condition_name}': {args}", file=sys.stderr)
                result = False # Treat invalid format as false
        elif intrinsic_function == "Fn::Or":
            if isinstance(args, list):
                # Evaluate all conditions in the list. At least one must be True for Fn::Or to be True.
                result = any(evaluate_condition(arg, template, context) for arg in args)
                print(f"    Info: Evaluated Fn::Or for '{condition_name}': {result}")
            else:
                print(f"    Warning: Invalid arguments for Fn::Or in condition '{condition_name}': {args}", file=sys.stderr)
                result = False # Treat invalid format as false
        elif intrinsic_function == "Fn::Not":
            if isinstance(args, list) and len(args) == 1:
                # Evaluate the single condition and negate the result.
                result = not evaluate_condition(args[0], template, context)
                print(f"    Info: Evaluated Fn::Not for '{condition_name}': {result}")
            else:
                print(f"    Warning: Invalid arguments for Fn::Not in condition '{condition_name}': {args}", file=sys.stderr)
                result = False # Treat invalid format as false
        elif intrinsic_function == "Fn::If":
             # Fn::If is handled in resolve_value, not evaluate_condition
             print(f"    Warning: Fn::If used directly in Conditions block for '{condition_name}'. This is not standard CloudFormation behavior. Returning False.", file=sys.stderr)
             result = False
        else:
            print(f"    Warning: Unknown intrinsic function '{intrinsic_function}' in condition '{condition_name}'. Returning False.", file=sys.stderr)
            result = False # Unknown functions evaluate to False

    elif isinstance(condition_definition, str):
        # Direct condition reference
        referenced_condition_name = condition_definition
        print(f"    Info: Condition '{condition_name}' is a direct reference to '{referenced_condition_name}'.")
        # Recursively evaluate the referenced condition
        try:
            result = evaluate_condition(referenced_condition_name, template, context)
        except ValueError as e:
            # If the referenced condition is not found, propagate the error
            raise ValueError(f"Condition '{condition_name}' references an unknown condition '{referenced_condition_name}'.") from e

    else:
        print(f"    Warning: Invalid condition definition format for '{condition_name}': {condition_definition}. Returning False.", file=sys.stderr)
        result = False # Invalid format evaluates to False

    # Store the result for memoization
    context['evaluated_conditions'][condition_name] = result
    return result


def parse_template_and_collect_actions(template_path, cfn_parameters, account_id, region, condition_input_values):
    """
    Parses the CloudFormation template and attempts to collect IAM actions
    and resource ARNs required for deployment.
    """
    print(f"\nParsing template: {template_path}...")
    actions_to_simulate = set()
    resource_arns_for_simulation = set()
    prerequisite_checks = []

    try:
        with open(template_path, 'r') as f:
            template = yaml.safe_load(f)
    except Exception as e:
        print(f"Error: Could not read or parse template file '{template_path}'. {e}", file=sys.stderr)
        sys.exit(1)

    template_parameters = template.get("Parameters", {})
    resources = template.get("Resources", {})
    conditions_block = template.get("Conditions", {}) # Store the Conditions block

    # Create a context dictionary to pass around relevant information
    context = {
        "account_id": account_id,
        "region": region,
        "parameters": {}, # Will be populated with resolved parameters
        "resources_in_template": resources,
        "conditions_block": conditions_block,
        "condition_input_values": condition_input_values # Store input values in context
    }

    # Substitute provided parameters with their defaults if not provided
    resolved_cfn_parameters = {}
    context["parameters"] = resolved_cfn_parameters # Add resolved parameters to context
    for param_key, param_def in template_parameters.items():
        if param_key in cfn_parameters:
            resolved_cfn_parameters[param_key] = cfn_cli_parameters[param_key]
        elif "Default" in param_def:
            resolved_cfn_parameters[param_key] = param_def["Default"]
        # Else, parameter is required but not provided - CloudFormation would fail.
        # This script relies on user providing them or them having defaults.

    # Check for required prerequisite parameters (example)
    if "OutpostRoleArn" in resolved_cfn_parameters:
        prerequisite_checks.append({
            "type": "iam_role_exists",
            "arn": resolved_cfn_parameters["OutpostRoleArn"],
            "description": "OutpostRoleArn parameter"
        })
    # Add more prerequisite checks based on other parameters if necessary

    print(f"Resolved CloudFormation Parameters for pre-flight checks: {resolved_cfn_parameters}")

    for logical_id, resource_def in resources.items():
        resource_type = resource_def.get("Type")
        properties = resource_def.get("Properties", {})

        print(f"  Processing resource: {logical_id} (Type: {resource_type})")

        if resource_type in RESOURCE_ACTION_MAP:
            map_entry = RESOURCE_ACTION_MAP[resource_type]

            if map_entry.get("type") == "CustomResource":
                # For Custom Resources, permissions are needed for the backing Lambda
                # Assuming the Lambda and its role are defined elsewhere in the template or pre-exist.
                # The critical part is creating the Custom Resource "registration" with CFN.
                # This typically doesn't require special IAM perms beyond what CFN itself needs,
                # unless specific service interactions are defined for the custom resource type.
                # The actual permissions are on the Lambda's execution role.
                # We will check for lambda:CreateFunction and iam:CreateRole for the Lambda exec role if defined.
                print(f"    Info: Custom Resource. Primary permissions are tied to its handler (Lambda).")
                # If the custom resource's handler Lambda and role are created IN THIS TEMPLATE,
                # their permissions will be checked when those AWS::Lambda::Function and AWS::IAM::Role are processed.
                actions_to_simulate.add("cloudformation:CreateStack") # General CFN permission
                continue


            # 1. Add generic actions for the resource type
            actions_to_simulate.update(map_entry.get("generic_actions", []))

            # 2. Construct resource ARN pattern for simulation
            arn_pattern_str = map_entry.get("arn_pattern", "arn:aws:*:{region}:{accountId}:{resourceLogicalIdPlaceholder}/*") # Default to broad if no pattern

            # Try to make ARN more specific using known properties or parameters
            # This is highly dependent on the resource type and its naming scheme
            resource_name_from_props = "*" # Default to wildcard
            if resource_type == "AWS::IAM::Role":
                role_name_val = properties.get("RoleName")
                if role_name_val:
                    resource_name_from_props = resolve_value(role_name_val, context["parameters"], context["account_id"], context["region"], context["resources_in_template"])
                else: # Role name will be auto-generated by CloudFormation
                    resource_name_from_props = f"{logical_id}-*" # Placeholder for CFN generated name
            elif resource_type == "AWS::S3::Bucket":
                bucket_name_val = properties.get("BucketName")
                if bucket_name_val:
                     resource_name_from_props = resolve_value(bucket_name_val, context["parameters"], context["account_id"], context["region"], context["resources_in_template"])
                 else: # Bucket name will be auto-generated. S3 ARNs don't typically include region/account like others.
                     arn_pattern_str = "arn:aws:s3:::{bucketNamePlaceholder}-*" # Special handling for S3 generated names
                     resource_name_from_props = "" # Bucket name is the main part for S3 ARN
             elif resource_type in ["AWS::SQS::Queue", "AWS::SNS::Topic", "AWS::CloudTrail::Trail", "AWS::Lambda::Function"]:
                 name_prop_key = None
                 if resource_type == "AWS::SQS::Queue": name_prop_key = "QueueName"
                 elif resource_type == "AWS::SNS::Topic": name_prop_key = "TopicName"
                 elif resource_type == "AWS::CloudTrail::Trail": name_prop_key = "TrailName" # TrailName is optional, CFN generates if absent
                 elif resource_type == "AWS::Lambda::Function": name_prop_key = "FunctionName"

                 if name_prop_key and properties.get(name_prop_key):
                     resource_name_from_props = resolve_value(properties.get(name_prop_key), context["parameters"], context["account_id"], context["region"], context["resources_in_template"])
                 else: # Name will be auto-generated by CloudFormation
                     resource_name_from_props = f"{logical_id}-*"

             # Resolve Account ID and Region from template context using resolve_value
             resolved_account_id = resolve_value({"Ref": "AWS::AccountId"}, context["parameters"], context["account_id"], context["region"], context["resources_in_template"])
             resolved_region = resolve_value({"Ref": "AWS::Region"}, context["parameters"], context["account_id"], context["region"], context["resources_in_template"])

            # Substitute placeholders in ARN pattern using resolved values
            # Ensure resolved values are strings, handle None for AWS::NoValue if it somehow appears here
            current_arn = arn_pattern_str.replace("{accountId}", str(resolved_account_id) if resolved_account_id is not None else "*") \
                                         .replace("{region}", str(resolved_region) if resolved_region is not None else "*") \
                                         .replace("{roleName}", str(resource_name_from_props)) \
                                         .replace("{policyName}", str(resource_name_from_props)) \
                                         .replace("{functionName}", str(resource_name_from_props)) \
                                         .replace("{bucketName}", str(resource_name_from_props)) \
                                         .replace("{queueName}", str(resource_name_from_props)) \
                                         .replace("{topicName}", str(resource_name_from_props)) \
                                         .replace("{trailName}", str(resource_name_from_props)) \
                                         .replace("{aliasName}", str(resource_name_from_props)) \
                                         .replace("{stackSetName}", str(resource_name_from_props)) \
                                         .replace("{resourceLogicalIdPlaceholder}", logical_id) # fallback placeholder

            # Specific handling for S3 ARN pattern if BucketName was empty and pattern was adjusted
            if resource_type == "AWS::S3::Bucket" and "{bucketNamePlaceholder}" in current_arn:
                 current_arn = current_arn.replace("{bucketNamePlaceholder}", f"cfn-{logical_id.lower()}")


            resource_arns_for_simulation.add(current_arn)
            # For some actions, like iam:PassRole, the resource is the role being passed, not the service using it.
            # And some actions apply globally (e.g. cloudformation:CreateStackSet)

            # 3. Check properties for specific actions (e.g., iam:PassRole)
            property_actions_map = map_entry.get("property_actions", {})
            for prop_key, prop_actions in property_actions_map.items():
                if prop_key in properties:
                    actions_to_simulate.update(prop_actions)
                    if prop_key == "Role" and "iam:PassRole" in prop_actions: # Special handling for PassRole
                        role_arn_to_pass = resolve_value(properties[prop_key], context["parameters"], context["account_id"], context["region"], context["resources_in_template"])
                        if isinstance(role_arn_to_pass, str) and role_arn_to_pass.startswith("arn:"):
                            resource_arns_for_simulation.add(role_arn_to_pass)
                        else:
                            # If it's a Ref to a role created in the same template, its ARN isn't known yet.
                            # The iam:PassRole action needs to be checked against the role that WILL be created.
                            # For simulation, you might need to construct a potential ARN or use a wildcard.
                            # This simplified version adds the role's logical ID or a wildcard ARN.
                            pass_role_placeholder_arn = f"arn:aws:iam::{account_id}:role/{role_arn_to_pass}-*"
                            resource_arns_for_simulation.add(pass_role_placeholder_arn)
                            print(f"    Info: Added potential PassRole ARN for simulation: {pass_role_placeholder_arn} (for role logical ID/name: {role_arn_to_pass})")

        # Handle Tags - common across many resources
        if "Tags" in properties:
            # The specific tag action varies (e.g., ec2:CreateTags, s3:PutBucketTagging, iam:TagRole)
            # For simplicity, we can try to add a generic one if not covered, or ensure the map_entry handles it.
            # Most Create actions in SDKs allow tags on creation, which is covered by Create<Resource> permission.
            # However, standalone tagging actions also exist.
            service_prefix = resource_type.split("::")[1].lower()
            # Common patterns: TagResource, CreateTags. Specific ones: s3:PutBucketTagging, iam:TagRole
            # This is a simplification. A more robust way is to ensure each resource_type in RESOURCE_ACTION_MAP lists its specific tagging action.
            if f"{service_prefix}:TagResource" not in actions_to_simulate and \
               f"{service_prefix}:CreateTags" not in actions_to_simulate and \
               not any(action.endswith("Tagging") or action.startswith(f"{service_prefix}:Tag") for action in map_entry.get("generic_actions",[])):
                actions_to_simulate.add(f"{service_prefix}:TagResource") # Generic, might not always be correct
                print(f"    Info: Added generic '{service_prefix}:TagResource' for Tags. Verify specific tagging permission for {resource_type}.")


        else:
            print(f"    Warning: No specific IAM action mapping found for resource type: {resource_type}. Add it to RESOURCE_ACTION_MAP.", file=sys.stderr)
            actions_to_simulate.add("cloudformation:CreateStack") # Fallback to general CFN permission

    return sorted(list(actions_to_simulate)), sorted(list(resource_arns_for_simulation)), prerequisite_checks


def check_prerequisites(checks, iam_client, region):
    """
    Checks for existence and basic configuration of prerequisite resources.
    """
    print("\n--- Checking Prerequisites ---")
    all_prereqs_ok = True
    for check in checks:
        print(f"  Checking: {check['description']} (ARN: {check['arn']})")
        if check["type"] == "iam_role_exists":
            try:
                iam_client.get_role(RoleName=check["arn"].split('/')[-1]) # Assumes ARN is last part
                print(f"    [PASS] Prerequisite IAM Role '{check['arn']}' exists.")
            except ClientError as e:
                if e.response['Error']['Code'] == 'NoSuchEntity':
                    print(f"    [FAIL] Prerequisite IAM Role '{check['arn']}' does not exist or is not accessible.")
                    all_prereqs_ok = False
                else:
                    print(f"    [ERROR] Error checking prerequisite IAM Role '{check['arn']}': {e}")
                    all_prereqs_ok = False
            except Exception as e:
                print(f"    [ERROR] Unexpected error checking prerequisite IAM Role '{check['arn']}': {e}")
                all_prereqs_ok = False
        # Add more prerequisite check types here
        # else:
        #     print(f"    Warning: Unknown prerequisite check type: {check['type']}", file=sys.stderr)

    if not checks:
        print("  No specific prerequisite resource checks defined or found from parameters.")
    elif all_prereqs_ok:
        print("  All checked prerequisites appear to be in place.")
    else:
        print("  Some prerequisite checks failed.")
    return all_prereqs_ok


def simulate_iam_permissions(iam_client, principal_arn, actions, resource_arns, context_entries=None):
    """
    Simulates IAM permissions for the given principal, actions, and resources.
    """
    print("\n--- Simulating IAM Permissions ---")
    print(f"  Principal ARN for Simulation: {principal_arn}")
    print(f"  Actions to Simulate ({len(actions)}): {actions}")
    print(f"  Resource ARNs for Simulation ({len(resource_arns)}): {resource_arns if resource_arns else ['*']}") # Use '*' if no specific ARNs

    if not actions:
        print("  No actions to simulate. Skipping IAM simulation.")
        return True, []

    # IAM simulation API has a limit on the number of actions and resources.
    # If lists are very long, they might need to be batched.
    # For this script, we'll try a single call. Max 100 actions. Max 100 resources. Max 50 context entries.

    try:
        simulation_input = {
            'PolicySourceArn': principal_arn,
            'ActionNames': actions,
            # If resource_arns is empty, simulation defaults to all resources ('*') for those actions.
            # Explicitly providing '*' if the list is empty can make the intent clearer.
            'ResourceArns': resource_arns if resource_arns else ['*']
        }
        if context_entries:
            simulation_input['ContextEntries'] = context_entries

        # print(f"DEBUG: Simulation Input: {json.dumps(simulation_input, indent=2)}")

        response = iam_client.simulate_principal_policy(**simulation_input)

        # print(f"DEBUG: Simulation Full Response: {json.dumps(response, indent=2)}")


        all_allowed = True
        failed_simulations = []

        print("\n  Simulation Results:")
        for eval_result in response.get('EvaluationResults', []):
            eval_action_name = eval_result['EvalActionName']
            eval_decision = eval_result['EvalDecision']
            eval_resource_name = eval_result.get('EvalResourceName', '*') # ResourceName might not always be present

            decision_marker = "[PASS]" if eval_decision == "allowed" else "[FAIL]"
            print(f"    {decision_marker} Action: {eval_action_name}, Resource: {eval_resource_name}, Decision: {eval_decision}")

            if eval_decision != "allowed":
                all_allowed = False
                failed_simulations.append(eval_result)
                # Log additional details if available
                if eval_result.get('OrganizationsDecisionDetail', {}).get('AllowedByOrganizations') == False:
                    print(f"      Denied by: Organizations SCP")
                if eval_result.get('PermissionsBoundaryDecisionDetail', {}).get('AllowedByPermissionsBoundary') == False:
                     print(f"      Denied by: Permissions Boundary")
                # MatchedStatements can give clues but are complex to parse concisely
                # if eval_result.get('MatchedStatements'):
                # print(f" Matched Statements: {eval_result['MatchedStatements']}")


        if all_allowed:
            print("\n  [SUCCESS] All simulated actions are allowed for the principal.")
        else:
            print("\n  [FAILURE] Some simulated actions were DENIED. Review details above.")

        return all_allowed, failed_simulations

    except ClientError as e:
        print(f"  [ERROR] IAM simulation failed: {e}", file=sys.stderr)
        # Common errors: InvalidInput - check ARNs, principal ARN, action names.
        # MalformedPolicyDocument if simulating with a custom policy.
        return False, [{"error": str(e)}]
    except Exception as e:
        print(f"  [ERROR] An unexpected error occurred during IAM simulation: {e}", file=sys.stderr)
        return False, [{"error": str(e)}]

def main():
    parser = argparse.ArgumentParser(description="Perform pre-flight checks for an AWS CloudFormation template.")
    parser.add_argument("--template-file", required=True, help="Path to the CloudFormation template (YAML/JSON).")
    parser.add_argument("--deploying-principal-arn", required=True, help="ARN of the IAM user/role that will deploy the stack.")
    parser.add_argument("--region", required=True, help="AWS Region for deployment and resource ARN construction.")
    parser.add_argument("--parameters", nargs='*', help="CloudFormation parameters as 'Key=Value' pairs (e.g., OutpostRoleArn=arn:aws:... ExternalID=myid).")
    parser.add_argument("--condition-values", help="JSON string of condition names and their boolean values (e.g., '{\"IsProduction\": true, \"UseCustomDomain\": false}').")
    parser.add_argument("--profile", help="AWS CLI profile to use.")
    # parser.add_argument("--stack-name", help="Proposed name for the CloudFormation stack.") # Could be used for more specific ARN construction

    args = parser.parse_args()

    # Initialize Boto3 session and clients
    try:
        session_params = {}
        if args.profile:
            session_params["profile_name"] = args.profile
        if args.region:
            session_params["region_name"] = args.region # Default region for clients

        session = boto3.Session(**session_params)
        iam_client = session.client("iam")
        sts_client = session.client("sts") # For Account ID
        print(f"Using AWS region: {session.region_name or 'Default from config'}")
    except PartialCredentialsError as e:
        print(f"Error: Incomplete AWS credentials found. Please configure your credentials. {e}", file=sys.stderr)
        sys.exit(1)
    except NoCredentialsError as e:
        print(f"Error: AWS credentials not found. Please configure your credentials. {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e: # Catch other potential boto3 session errors like profile not found
        print(f"Error: Could not initialize AWS session. {e}", file=sys.stderr)
        sys.exit(1)


    account_id = get_aws_account_id(sts_client)

    # Parse CLI parameters into a dictionary
    cfn_cli_parameters = {}
    if args.parameters:
        for p_item in args.parameters:
            if "=" not in p_item:
                print(f"Error: Parameter '{p_item}' is not in Key=Value format.", file=sys.stderr)
                sys.exit(1)
            key, value = p_item.split("=", 1)
            cfn_cli_parameters[key] = value

    # Parse condition values from JSON string
    condition_input_values = {}
    if args.condition_values:
        try:
            condition_input_values = json.loads(args.condition_values)
            if not isinstance(condition_input_values, dict):
                 raise ValueError("Condition values must be a JSON object.")
            # Ensure all values are boolean
            for key, value in condition_input_values.items():
                if not isinstance(value, bool):
                    raise ValueError(f"Value for condition '{key}' is not a boolean.")
        except json.JSONDecodeError as e:
            print(f"Error: Could not parse --condition-values JSON string. {e}", file=sys.stderr)
            sys.exit(1)
        except ValueError as e:
            print(f"Error: Invalid --condition-values format. {e}", file=sys.stderr)
            sys.exit(1)

    # --- Step 1: Parse Template & Collect Actions/Resource Info ---
    # Pass condition_input_values to the parsing function
    actions, resource_arns, prerequisite_action_checks = parse_template_and_collect_actions(
        args.template_file, cfn_cli_parameters, account_id, args.region, condition_input_values
    )

    # --- Step 2: Check Prerequisites (e.g., existence of roles from parameters) ---
    prereqs_ok = check_prerequisites(prerequisite_action_checks, iam_client, args.region)

    # --- Step 3: Simulate IAM Permissions ---
    # Construct context entries if needed, e.g., for sts:ExternalId or aws:RequestTag
    context_entries = []
    if "ExternalID" in cfn_cli_parameters and cfn_cli_parameters["ExternalID"]:
        context_entries.append({
            "ContextKeyName": "sts:ExternalId",
            "ContextKeyValues": [cfn_cli_parameters["ExternalID"]],
            "ContextKeyType": "string"
        })
    # Example for RequestTag - this is more complex as tag keys/values vary
    # context_entries.append({
    #     "ContextKeyName": "aws:RequestTag/managed_by",
    #     "ContextKeyValues": ["paloaltonetworks"],
    #     "ContextKeyType": "string"
    # })

    permissions_ok, failed_sims = simulate_iam_permissions(
        iam_client, args.deploying_principal_arn, actions, resource_arns, context_entries
    )

    # --- Final Summary ---
    print("\n--- Pre-flight Check Summary ---")
    if prereqs_ok:
        print("[PASS] Prerequisite checks passed or no specific prerequisites to check.")
    else:
        print("[FAIL] Some prerequisite checks failed.")

    if permissions_ok:
        print("[PASS] IAM permission simulation indicates the deploying principal has the necessary permissions for the identified actions and resources.")
    else:
        print("[FAIL] IAM permission simulation indicates some permissions are MISSING.")
        print("        Review the simulation details above for denied actions.")

    if prereqs_ok and permissions_ok:
        print("\nPre-flight checks completed successfully. Deployment is likely to proceed regarding these checks.")
        sys.exit(0)
    else:
        print("\nPre-flight checks identified potential issues. Review failures before attempting deployment.")
        sys.exit(1)

if __name__ == "__main__":
    main()
