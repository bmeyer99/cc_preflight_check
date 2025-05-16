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
def resolve_value(value, parameters, account_id, region, resources_in_template):
    if isinstance(value, dict):
        if "Ref" in value:
            ref_val = value["Ref"]
            if ref_val in parameters:
                # Parameter reference - return the resolved parameter value (includes defaults)
                return parameters[ref_val]
            if ref_val in resources_in_template:
                # Resource reference - return a placeholder ARN
                # Using a consistent placeholder format
                return f"arn:aws:::resolved-ref-{ref_val.lower()}"
            # Unresolved Ref - neither a parameter nor a resource in the template
            print(f"Warning: Unresolved Ref: {ref_val}", file=sys.stderr)
            return f"UNRESOLVED_REF_FOR_{ref_val}"
        elif "Fn::Sub" in value:
            sub_val = value["Fn::Sub"]
            # Extremely simplified Sub - only handles direct replacements of global/params
            # Does not handle the list form of Fn::Sub or complex expressions.
            if isinstance(sub_val, str):
                resolved_sub = sub_val
                resolved_sub = resolved_sub.replace("${AWS::AccountId}", account_id)
                resolved_sub = resolved_sub.replace("${AWS::Region}", region)
                for pk, pv in parameters.items():
                    resolved_sub = resolved_sub.replace(f"${{{pk}}}", str(pv))
                
                # Attempt to resolve resource Refs within Sub strings
                # e.g., "arn:aws:s3:::${MyBucket}"
                def replace_ref_in_sub(match):
                    ref_name = match.group(1)
                    if ref_name in parameters:
                        return str(parameters[ref_name])
                    # Here you might want to return a placeholder for resource logical IDs
                    # if you can't fully resolve them to ARNs during pre-flight.
                    # For now, just return the reference itself if not a parameter.
                    return f"${{{ref_name}}}" # Or a more specific placeholder

                resolved_sub = re.sub(r"\$\{(.+?)\}", replace_ref_in_sub, resolved_sub)
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
            resolved_list = [str(resolve_value(item, parameters, account_id, region, resources_in_template)) for item in list_to_join]
            return delimiter.join(resolved_list)

        # Recurse for nested structures
        return {k: resolve_value(v, parameters, account_id, region, resources_in_template) for k, v in value.items()}
    elif isinstance(value, list):
        return [resolve_value(item, parameters, account_id, region, resources_in_template) for item in value]
    return value


def parse_template_and_collect_actions(template_path, cfn_parameters, account_id, region):
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
    
    # Substitute provided parameters with their defaults if not provided
    resolved_cfn_parameters = {}
    for param_key, param_def in template_parameters.items():
        if param_key in cfn_parameters:
            resolved_cfn_parameters[param_key] = cfn_parameters[param_key]
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
                    resource_name_from_props = resolve_value(role_name_val, resolved_cfn_parameters, account_id, region, resources)
                else: # Role name will be auto-generated by CloudFormation
                    resource_name_from_props = f"{logical_id}-*" # Placeholder for CFN generated name
            elif resource_type == "AWS::S3::Bucket":
                bucket_name_val = properties.get("BucketName")
                if bucket_name_val:
                     resource_name_from_props = resolve_value(bucket_name_val, resolved_cfn_parameters, account_id, region, resources)
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
                    resource_name_from_props = resolve_value(properties.get(name_prop_key), resolved_cfn_parameters, account_id, region, resources)
                else: # Name will be auto-generated by CloudFormation
                    resource_name_from_props = f"{logical_id}-*"
            
            # Substitute placeholders in ARN pattern
            # Ensure resource_name_from_props is a string
            current_arn = arn_pattern_str.replace("{accountId}", account_id or "*") \
                                         .replace("{region}", region or "*") \
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
                        role_arn_to_pass = resolve_value(properties[prop_key], resolved_cfn_parameters, account_id, region, resources)
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
    
    # --- Step 1: Parse Template & Collect Actions/Resource Info ---
    actions, resource_arns, prerequisite_action_checks = parse_template_and_collect_actions(
        args.template_file, cfn_cli_parameters, account_id, args.region
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
