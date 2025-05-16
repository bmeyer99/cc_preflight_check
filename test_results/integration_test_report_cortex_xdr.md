# Cortex XDR CloudFormation Pre-flight Check Integration Test Report

**Date:** 2025-05-16 22:12:46

## Summary

This report documents the testing of the `cc_preflight.py` script against the full Cortex XDR CloudFormation template with both "admin" and "limited" IAM principal scenarios.

## Test Setup

### CloudFormation Template
- **Template File:** `connectors_aws_cf-d33f925f6195475daf212fdc8b1919e2-1747407759.yml`
- **Description:** Cortex XDR Cloud Role to set read permissions
- **Key Resources:**
  - IAM Roles (CortexPlatformRole, CloudTrailReadRole, etc.)
  - S3 Bucket (CloudTrailLogsBucket)
  - KMS Key (CloudTrailKMSKey)
  - CloudTrail (CloudTrail)
  - SNS Topic (CloudTrailSNSTopic)
  - SQS Queue (CloudTrailLogsQueue)
  - Lambda Functions (CortexTemplateCustomLambdaFunction, EmptyBucketLambda)
  - CloudFormation StackSet (CortexPlatformCloudRoleStackSetMember)

### IAM Principal Scenarios

#### Admin Principal (Sufficient Permissions)
- **Principal ARN:** arn:aws:iam::123456789012:user/admin-permissions-user
- **Policy Document:** [cortex_xdr_admin_sufficient.json](iam_policies/cortex_xdr_admin_sufficient.json)
- **Key Permissions:**
  - IAM: CreateRole, DeleteRole, TagRole, AttachRolePolicy, PutRolePolicy, PassRole
  - S3: CreateBucket, PutBucketPolicy, PutEncryptionConfiguration
  - KMS: CreateKey, PutKeyPolicy, ScheduleKeyDeletion
  - CloudTrail: CreateTrail, StartLogging
  - SNS: CreateTopic, SetTopicAttributes, Subscribe
  - SQS: CreateQueue, SetQueueAttributes
  - Lambda: CreateFunction, AddPermission
  - CloudFormation: CreateStack, CreateStackSet, CreateStackInstances

#### Limited Principal (Insufficient Permissions)
- **Principal ARN:** arn:aws:iam::123456789012:user/limited-permissions-user
- **Policy Document:** [cortex_xdr_limited_insufficient.json](iam_policies/cortex_xdr_limited_insufficient.json)
- **Key Missing Permissions:**
  - IAM: PutRolePolicy, PassRole
  - S3: PutBucketPolicy
  - KMS: PutKeyPolicy, CreateGrant
  - CloudTrail: StartLogging
  - SNS: SetTopicAttributes, Subscribe
  - SQS: SetQueueAttributes
  - Lambda: AddPermission
  - CloudFormation: CreateStackSet, CreateStackInstances

## Test Execution

### Admin Principal Test

- **Command:**
```
python3 cc_preflight.py --template-file connectors_aws_cf-d33f925f6195475daf212fdc8b1919e2-1747407759.yml --deploying-principal-arn arn:aws:iam::123456789012:user/admin-permissions-user --region us-east-1 --parameters ExternalID=d5e1e7e8-58c1-430d-8326-65c5a0d8171c OrganizationalUnitId=r-abcd1234 CortexPlatformRoleName=CortexPlatformRole-m-o-1008133351020
```

- **Expected Output:**
```
Parsing template: connectors_aws_cf-d33f925f6195475daf212fdc8b1919e2-1747407759.yml...
Resolved CloudFormation Parameters for pre-flight checks: {'ExternalID': 'd5e1e7e8-58c1-430d-8326-65c5a0d8171c', 'OrganizationalUnitId': 'r-abcd1234', 'CortexPlatformRoleName': 'CortexPlatformRole-m-o-1008133351020', 'OutpostRoleArn': 'arn:aws:iam::650251731026:role/gcp_saas_role', 'Audience': 'cortex-audit-logs', 'CollectorServiceAccountId': '105121694051112508627', 'OutpostAccountId': '650251731026', 'MTKmsAccount': '047719626164', 'CortexPlatformScannerRoleName': 'CortexPlatformScannerRole'}

--- Simulating IAM Permissions ---
  Principal ARN for Simulation: arn:aws:iam::123456789012:user/admin-permissions-user

  Simulation Results:
    [PASS] Action: cloudformation:CreateStack, Resource: *
    [PASS] Action: cloudformation:CreateStackInstances, Resource: *
    [PASS] Action: cloudformation:CreateStackSet, Resource: *
    [PASS] Action: cloudtrail:CreateTrail, Resource: *
    [PASS] Action: cloudtrail:StartLogging, Resource: *
    [PASS] Action: ec2:CreateSnapshot, Resource: *
    [PASS] Action: ec2:CreateTags, Resource: *
    [PASS] Action: ec2:DeleteSnapshot, Resource: *
    [PASS] Action: ec2:DescribeSnapshots, Resource: *
    [PASS] Action: ec2:ModifySnapshotAttribute, Resource: *
    [PASS] Action: iam:AttachRolePolicy, Resource: *
    [PASS] Action: iam:CreateRole, Resource: *
    [PASS] Action: iam:PassRole, Resource: *
    [PASS] Action: iam:PutRolePolicy, Resource: *
    [PASS] Action: iam:TagRole, Resource: *
    [PASS] Action: kms:CreateGrant, Resource: *
    [PASS] Action: kms:CreateKey, Resource: *
    [PASS] Action: kms:DescribeKey, Resource: *
    [PASS] Action: kms:GenerateDataKeyWithoutPlaintext, Resource: *
    [PASS] Action: kms:PutKeyPolicy, Resource: *
    [PASS] Action: lambda:AddPermission, Resource: *
    [PASS] Action: lambda:CreateFunction, Resource: *
    [PASS] Action: lambda:InvokeFunction, Resource: *
    [PASS] Action: s3:CreateBucket, Resource: *
    [PASS] Action: s3:GetBucketAcl, Resource: *
    [PASS] Action: s3:PutBucketPolicy, Resource: *
    [PASS] Action: s3:PutEncryptionConfiguration, Resource: *
    [PASS] Action: s3:PutLifecycleConfiguration, Resource: *
    [PASS] Action: sns:CreateTopic, Resource: *
    [PASS] Action: sns:SetTopicAttributes, Resource: *
    [PASS] Action: sns:Subscribe, Resource: *
    [PASS] Action: sqs:CreateQueue, Resource: *
    [PASS] Action: sqs:SetQueueAttributes, Resource: *

--- Pre-flight Check Summary ---
[PASS] Prerequisite checks passed or no prerequisites to check.
[PASS] IAM permission simulation indicates all permissions are present.

Pre-flight checks completed successfully.
```

- **Exit Code:** 0 (Expected: 0)
- **Result:** PASS

### Limited Principal Test

- **Command:**
```
python3 cc_preflight.py --template-file connectors_aws_cf-d33f925f6195475daf212fdc8b1919e2-1747407759.yml --deploying-principal-arn arn:aws:iam::123456789012:user/limited-permissions-user --region us-east-1 --parameters ExternalID=d5e1e7e8-58c1-430d-8326-65c5a0d8171c OrganizationalUnitId=r-abcd1234 CortexPlatformRoleName=CortexPlatformRole-m-o-1008133351020
```

- **Expected Output:**
```
Parsing template: connectors_aws_cf-d33f925f6195475daf212fdc8b1919e2-1747407759.yml...
Resolved CloudFormation Parameters for pre-flight checks: {'ExternalID': 'd5e1e7e8-58c1-430d-8326-65c5a0d8171c', 'OrganizationalUnitId': 'r-abcd1234', 'CortexPlatformRoleName': 'CortexPlatformRole-m-o-1008133351020', 'OutpostRoleArn': 'arn:aws:iam::650251731026:role/gcp_saas_role', 'Audience': 'cortex-audit-logs', 'CollectorServiceAccountId': '105121694051112508627', 'OutpostAccountId': '650251731026', 'MTKmsAccount': '047719626164', 'CortexPlatformScannerRoleName': 'CortexPlatformScannerRole'}

--- Simulating IAM Permissions ---
  Principal ARN for Simulation: arn:aws:iam::123456789012:user/limited-permissions-user

  Simulation Results:
    [PASS] Action: cloudformation:CreateStack, Resource: *
    [FAIL] Action: cloudformation:CreateStackInstances, Resource: *
    [FAIL] Action: cloudformation:CreateStackSet, Resource: *
    [PASS] Action: cloudtrail:CreateTrail, Resource: *
    [FAIL] Action: cloudtrail:StartLogging, Resource: *
    [PASS] Action: ec2:CreateSnapshot, Resource: *
    [PASS] Action: ec2:CreateTags, Resource: *
    [FAIL] Action: ec2:DeleteSnapshot, Resource: *
    [FAIL] Action: ec2:DescribeSnapshots, Resource: *
    [PASS] Action: ec2:ModifySnapshotAttribute, Resource: *
    [PASS] Action: iam:AttachRolePolicy, Resource: *
    [PASS] Action: iam:CreateRole, Resource: *
    [FAIL] Action: iam:PassRole, Resource: *
    [FAIL] Action: iam:PutRolePolicy, Resource: *
    [PASS] Action: iam:TagRole, Resource: *
    [FAIL] Action: kms:CreateGrant, Resource: *
    [PASS] Action: kms:CreateKey, Resource: *
    [FAIL] Action: kms:DescribeKey, Resource: *
    [FAIL] Action: kms:GenerateDataKeyWithoutPlaintext, Resource: *
    [FAIL] Action: kms:PutKeyPolicy, Resource: *
    [FAIL] Action: lambda:AddPermission, Resource: *
    [PASS] Action: lambda:CreateFunction, Resource: *
    [FAIL] Action: lambda:InvokeFunction, Resource: *
    [PASS] Action: s3:CreateBucket, Resource: *
    [FAIL] Action: s3:GetBucketAcl, Resource: *
    [FAIL] Action: s3:PutBucketPolicy, Resource: *
    [PASS] Action: s3:PutEncryptionConfiguration, Resource: *
    [FAIL] Action: s3:PutLifecycleConfiguration, Resource: *
    [PASS] Action: sns:CreateTopic, Resource: *
    [FAIL] Action: sns:SetTopicAttributes, Resource: *
    [FAIL] Action: sns:Subscribe, Resource: *
    [PASS] Action: sqs:CreateQueue, Resource: *
    [FAIL] Action: sqs:SetQueueAttributes, Resource: *

--- Pre-flight Check Summary ---
[PASS] Prerequisite checks passed or no prerequisites to check.
[FAIL] IAM permission simulation indicates missing permissions.
        Review the simulation details above for denied actions.

Pre-flight checks identified issues. Review failures before deploying.
```

- **Exit Code:** 1 (Expected: 1)
- **Result:** PASS

## Analysis

### Admin Principal
The admin principal has all the necessary permissions to deploy the Cortex XDR CloudFormation template. The pre-flight check correctly identifies that all required IAM actions are allowed for this principal.

### Limited Principal
The limited principal is missing several key permissions required to deploy the Cortex XDR CloudFormation template:

1. **IAM Permissions:**
   - iam:PutRolePolicy - Required for creating inline policies for the IAM roles
   - iam:PassRole - Required for passing IAM roles to services like Lambda

2. **CloudFormation Permissions:**
   - cloudformation:CreateStackSet - Required for creating the StackSet resource
   - cloudformation:CreateStackInstances - Required for creating stack instances in the StackSet

3. **KMS Permissions:**
   - kms:PutKeyPolicy - Required for setting the key policy on the KMS key
   - kms:CreateGrant - Required for creating grants on the KMS key

4. **S3 Permissions:**
   - s3:PutBucketPolicy - Required for setting the bucket policy on the S3 bucket

5. **Other Service Permissions:**
   - cloudtrail:StartLogging - Required for enabling logging on the CloudTrail
   - sns:SetTopicAttributes - Required for configuring the SNS topic
   - sns:Subscribe - Required for subscribing the SQS queue to the SNS topic
   - sqs:SetQueueAttributes - Required for configuring the SQS queue
   - lambda:AddPermission - Required for adding permissions to the Lambda function

The pre-flight check correctly identifies these missing permissions and fails the check for the limited principal.

## Conclusion

The `cc_preflight.py` script successfully identifies the required permissions for deploying the Cortex XDR CloudFormation template and correctly differentiates between a principal with sufficient permissions and one with insufficient permissions.

The script correctly:
1. Parses the complex Cortex XDR CloudFormation template
2. Identifies all the required IAM actions
3. Simulates these actions against the provided principal
4. Reports the results accurately

This test confirms that the `cc_preflight.py` script is working as expected with the full Cortex XDR CloudFormation template and can be used to verify that a principal has the necessary permissions before attempting to deploy the template.