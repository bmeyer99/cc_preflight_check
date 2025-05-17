"""
AWS CloudFormation Resource Action Map.

This module defines a mapping between CloudFormation resource types and the IAM actions
required to create, update, delete, and tag those resources. It also includes ARN patterns
for constructing resource ARNs for IAM policy simulation.

The RESOURCE_ACTION_MAP dictionary is the core data structure of this module, providing:
1. Generic IAM actions required for each resource type
2. ARN patterns for constructing resource ARNs
3. Property-specific IAM actions for resource properties
4. Operation-specific IAM actions (Create, Update, Delete, Tag)
5. Special handling for custom resources

This mapping is used by the cc_preflight.py module to determine which IAM permissions
are required to deploy a CloudFormation template based on the resources it contains.
"""

from typing import Dict, List, Any

# Map of CloudFormation resource types to their required IAM actions and ARN patterns
RESOURCE_ACTION_MAP: Dict[str, Dict[str, Any]] = {
    # The RESOURCE_ACTION_MAP dictionary has the following structure:
    # {
    #     "AWS::Service::ResourceType": {
    #         "generic_actions": [list of IAM actions required for this resource type],
    #         "arn_pattern": "ARN pattern with placeholders like {accountId}, {region}",
    #         "property_actions": {
    #             "PropertyName": [list of IAM actions required for this property]
    #         },
    #         "operation_actions": {
    #             "Create": [list of IAM actions for creation],
    #             "Update": [list of IAM actions for updates],
    #             "Delete": [list of IAM actions for deletion],
    #             "Tag": [list of IAM actions for tagging]
    #         }
    #     }
    # }
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
    # The "type": "CustomResource" flag indicates special handling in cc_preflight.py
    "Custom::PublishRoleDetail": {
        "type": "CustomResource",
        "operation_actions": {
            "Create": ["organizations:DescribeOrganization", "s3:PutObject"],
            "Update": ["organizations:DescribeOrganization", "s3:PutObject"],
            "Delete": [],
            "Tag": []
        }
    },
    "Custom::EmptyBucketDetails": { "type": "CustomResource" },
    
    # EC2 resources needed for Cortex Cloud ADS (Agentless Workload Scanning)
    "AWS::EC2::Snapshot": {
        "generic_actions": [
            "ec2:CreateSnapshot",
            "ec2:DeleteSnapshot",
            "ec2:ModifySnapshotAttribute",
            "ec2:DescribeSnapshots",
            "ec2:CopySnapshot",
            "ec2:CreateTags"
        ],
        "arn_pattern": "arn:aws:ec2:{region}:{accountId}:snapshot/{snapshotId}",
        "property_actions": {
            "Tags": ["ec2:CreateTags"]
        },
        "operation_actions": {
            "Create": ["ec2:CreateSnapshot", "ec2:CreateTags"],
            "Update": ["ec2:ModifySnapshotAttribute"],
            "Delete": ["ec2:DeleteSnapshot"],
            "Tag": ["ec2:CreateTags"]
        }
    },
    
    # RDS resources needed for Cortex Cloud DSPM (Data Security Posture Management)
    "AWS::RDS::DBSnapshot": {
        "generic_actions": [
            "rds:CreateDBSnapshot",
            "rds:DeleteDBSnapshot",
            "rds:DescribeDBSnapshots",
            "rds:AddTagsToResource"
        ],
        "arn_pattern": "arn:aws:rds:{region}:{accountId}:snapshot:{snapshotName}",
        "property_actions": {
            "Tags": ["rds:AddTagsToResource"]
        },
        "operation_actions": {
            "Create": ["rds:CreateDBSnapshot", "rds:AddTagsToResource"],
            "Update": ["rds:AddTagsToResource"],
            "Delete": ["rds:DeleteDBSnapshot"],
            "Tag": ["rds:AddTagsToResource"]
        }
    },
    
    "AWS::RDS::DBClusterSnapshot": {
        "generic_actions": [
            "rds:CreateDBClusterSnapshot",
            "rds:DeleteDBClusterSnapshot",
            "rds:DescribeDBClusterSnapshots",
            "rds:AddTagsToResource"
        ],
        "arn_pattern": "arn:aws:rds:{region}:{accountId}:cluster-snapshot:{snapshotName}",
        "property_actions": {
            "Tags": ["rds:AddTagsToResource"]
        },
        "operation_actions": {
            "Create": ["rds:CreateDBClusterSnapshot", "rds:AddTagsToResource"],
            "Update": ["rds:AddTagsToResource"],
            "Delete": ["rds:DeleteDBClusterSnapshot"],
            "Tag": ["rds:AddTagsToResource"]
        }
    },
    
    # ECR resources needed for Cortex Cloud Registry Scan
    "AWS::ECR::Repository": {
        "generic_actions": [
            "ecr:CreateRepository",
            "ecr:DeleteRepository",
            "ecr:DescribeRepositories",
            "ecr:TagResource",
            "ecr:UntagResource",
            "ecr:GetAuthorizationToken",
            "ecr:BatchGetImage",
            "ecr:GetDownloadUrlForLayer"
        ],
        "arn_pattern": "arn:aws:ecr:{region}:{accountId}:repository/{repositoryName}",
        "property_actions": {
            "RepositoryPolicyText": ["ecr:SetRepositoryPolicy", "ecr:GetRepositoryPolicy"],
            "LifecyclePolicy": ["ecr:PutLifecyclePolicy", "ecr:GetLifecyclePolicy"]
        },
        "operation_actions": {
            "Create": ["ecr:CreateRepository", "ecr:TagResource"],
            "Update": ["ecr:PutLifecyclePolicy", "ecr:SetRepositoryPolicy", "ecr:TagResource", "ecr:UntagResource"],
            "Delete": ["ecr:DeleteRepository"],
            "Tag": ["ecr:TagResource", "ecr:UntagResource"]
        }
    },
    
    # Additional S3 operations needed for Cortex Cloud DSPM and Log Collection
    "AWS::S3::Object": {
        "generic_actions": [
            "s3:PutObject",
            "s3:GetObject",
            "s3:DeleteObject",
            "s3:ListBucket",
            "s3:GetBucketLocation"
        ],
        "arn_pattern": "arn:aws:s3:::{bucketName}/{objectKey}",
        "property_actions": {},
        "operation_actions": {
            "Create": ["s3:PutObject"],
            "Update": ["s3:PutObject"],
            "Delete": ["s3:DeleteObject"],
            "Tag": []
        }
    }
}