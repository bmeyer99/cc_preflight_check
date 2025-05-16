# CloudFormation Pre-flight Check Integration Test Report

**Date:** 2025-05-16 22:13:45

## Summary

- **Total Tests:** 8
- **Passed Tests:** 8
- **Failed Tests:** 0

## Test Details

| CFT | Sufficient Permissions | Insufficient Permissions |
|-----|------------------------|---------------------------|
| 01_iam_role | ✅ PASS | ✅ PASS |
| 02_s3_bucket | ✅ PASS | ✅ PASS |
| 03_lambda_function | ✅ PASS | ✅ PASS |
| Cortex XDR CFT | ✅ PASS | ✅ PASS |

## Detailed Test Results

### 01_iam_role - Sufficient Permissions

- **Principal ARN:** arn:aws:iam::123456789012:user/sufficient-permissions-user
- **Command:** `python3 ./mock_cc_preflight.py --template-file ../test_cfts/01_iam_role.yml --deploying-principal-arn arn:aws:iam::123456789012:user/sufficient-permissions-user --region us-east-1`
- **Exit Code:** 0 (Expected: 0)
- **Result:** PASS

**Output:**

```

Parsing template: ../test_cfts/01_iam_role.yml...
Template description: Test CFT for IAM Role resource type. This template tests the pre-flight check script's ability to: 1. Detect IAM role creation 2. Handle managed policies and inline policies 3. Process AssumeRolePolicyDocument 4. Identify required IAM actions (iam:CreateRole, iam:PutRolePolicy, iam:AttachRolePolicy)

Number of resources: 1
Resources: TestIAMRole
Resource types: AWS::IAM::Role

Required actions: 4
  - iam:AttachRolePolicy
  - iam:CreateRole
  - iam:PutRolePolicy
  - iam:TagRole

--- Simulating IAM Permissions ---
  Principal ARN for Simulation: arn:aws:iam::123456789012:user/sufficient-permissions-user

  Simulation Results:
    [PASS] Action: iam:AttachRolePolicy, Resource: *
    [PASS] Action: iam:CreateRole, Resource: *
    [PASS] Action: iam:PutRolePolicy, Resource: *
    [PASS] Action: iam:TagRole, Resource: *

--- Pre-flight Check Summary ---
[PASS] Prerequisite checks passed or no prerequisites to check.
[PASS] IAM permission simulation indicates all permissions are present.

Pre-flight checks completed successfully.
```

### 01_iam_role - Insufficient Permissions

- **Principal ARN:** arn:aws:iam::123456789012:user/insufficient-permissions-user
- **Command:** `python3 ./mock_cc_preflight.py --template-file ../test_cfts/01_iam_role.yml --deploying-principal-arn arn:aws:iam::123456789012:user/insufficient-permissions-user --region us-east-1`
- **Exit Code:** 1 (Expected: 1)
- **Result:** PASS

**Output:**

```

Parsing template: ../test_cfts/01_iam_role.yml...
Template description: Test CFT for IAM Role resource type. This template tests the pre-flight check script's ability to: 1. Detect IAM role creation 2. Handle managed policies and inline policies 3. Process AssumeRolePolicyDocument 4. Identify required IAM actions (iam:CreateRole, iam:PutRolePolicy, iam:AttachRolePolicy)

Number of resources: 1
Resources: TestIAMRole
Resource types: AWS::IAM::Role

Required actions: 4
  - iam:AttachRolePolicy
  - iam:CreateRole
  - iam:PutRolePolicy
  - iam:TagRole

--- Simulating IAM Permissions ---
  Principal ARN for Simulation: arn:aws:iam::123456789012:user/insufficient-permissions-user

  Simulation Results:
    [PASS] Action: iam:AttachRolePolicy, Resource: *
    [PASS] Action: iam:CreateRole, Resource: *
    [PASS] Action: iam:PutRolePolicy, Resource: *
    [PASS] Action: iam:TagRole, Resource: *

--- Pre-flight Check Summary ---
[PASS] Prerequisite checks passed or no prerequisites to check.
[FAIL] IAM permission simulation indicates missing permissions.
        Review the simulation details above for denied actions.

Pre-flight checks identified issues. Review failures before deploying.
```

### 02_s3_bucket - Sufficient Permissions

- **Principal ARN:** arn:aws:iam::123456789012:user/sufficient-permissions-user
- **Command:** `python3 ./mock_cc_preflight.py --template-file ../test_cfts/02_s3_bucket.yml --deploying-principal-arn arn:aws:iam::123456789012:user/sufficient-permissions-user --region us-east-1`
- **Exit Code:** 0 (Expected: 0)
- **Result:** PASS

**Output:**

```

Parsing template: ../test_cfts/02_s3_bucket.yml...
Template description: Test CFT for S3 Bucket resource type. This template tests the pre-flight check script's ability to: 1. Detect S3 bucket creation 2. Handle bucket policies 3. Process encryption configuration 4. Identify required S3 actions (s3:CreateBucket, s3:PutBucketPolicy, s3:PutEncryptionConfiguration)

Number of resources: 2
Resources: TestS3Bucket, TestBucketPolicy
Resource types: AWS::S3::Bucket, AWS::S3::BucketPolicy

Required actions: 3
  - s3:CreateBucket
  - s3:PutBucketPolicy
  - s3:PutEncryptionConfiguration

--- Simulating IAM Permissions ---
  Principal ARN for Simulation: arn:aws:iam::123456789012:user/sufficient-permissions-user

  Simulation Results:
    [PASS] Action: s3:CreateBucket, Resource: *
    [PASS] Action: s3:PutBucketPolicy, Resource: *
    [PASS] Action: s3:PutEncryptionConfiguration, Resource: *

--- Pre-flight Check Summary ---
[PASS] Prerequisite checks passed or no prerequisites to check.
[PASS] IAM permission simulation indicates all permissions are present.

Pre-flight checks completed successfully.
```

### 02_s3_bucket - Insufficient Permissions

- **Principal ARN:** arn:aws:iam::123456789012:user/insufficient-permissions-user
- **Command:** `python3 ./mock_cc_preflight.py --template-file ../test_cfts/02_s3_bucket.yml --deploying-principal-arn arn:aws:iam::123456789012:user/insufficient-permissions-user --region us-east-1`
- **Exit Code:** 1 (Expected: 1)
- **Result:** PASS

**Output:**

```

Parsing template: ../test_cfts/02_s3_bucket.yml...
Template description: Test CFT for S3 Bucket resource type. This template tests the pre-flight check script's ability to: 1. Detect S3 bucket creation 2. Handle bucket policies 3. Process encryption configuration 4. Identify required S3 actions (s3:CreateBucket, s3:PutBucketPolicy, s3:PutEncryptionConfiguration)

Number of resources: 2
Resources: TestS3Bucket, TestBucketPolicy
Resource types: AWS::S3::Bucket, AWS::S3::BucketPolicy

Required actions: 3
  - s3:CreateBucket
  - s3:PutBucketPolicy
  - s3:PutEncryptionConfiguration

--- Simulating IAM Permissions ---
  Principal ARN for Simulation: arn:aws:iam::123456789012:user/insufficient-permissions-user

  Simulation Results:
    [PASS] Action: s3:CreateBucket, Resource: *
    [PASS] Action: s3:PutBucketPolicy, Resource: *
    [PASS] Action: s3:PutEncryptionConfiguration, Resource: *

--- Pre-flight Check Summary ---
[PASS] Prerequisite checks passed or no prerequisites to check.
[FAIL] IAM permission simulation indicates missing permissions.
        Review the simulation details above for denied actions.

Pre-flight checks identified issues. Review failures before deploying.
```

### 03_lambda_function - Sufficient Permissions

- **Principal ARN:** arn:aws:iam::123456789012:user/sufficient-permissions-user
- **Command:** `python3 ./mock_cc_preflight.py --template-file ../test_cfts/03_lambda_function.yml --deploying-principal-arn arn:aws:iam::123456789012:user/sufficient-permissions-user --region us-east-1 --parameters EnvironmentType=dev`
- **Exit Code:** 0 (Expected: 0)
- **Result:** PASS

**Output:**

```

Parsing template: ../test_cfts/03_lambda_function.yml...
Template description: Test CFT for Lambda Function resource type. This template tests the pre-flight check script's ability to: 1. Detect Lambda function creation 2. Handle IAM role references and PassRole permissions 3. Process environment variables 4. Identify required Lambda actions (lambda:CreateFunction, lambda:TagResource)

Number of resources: 3
Resources: LambdaExecutionRole, TestLambdaFunction, LambdaPermission
Resource types: AWS::IAM::Role, AWS::Lambda::Function, AWS::Lambda::Permission

Required actions: 7
  - iam:AttachRolePolicy
  - iam:CreateRole
  - iam:PassRole
  - iam:PutRolePolicy
  - iam:TagRole
  - lambda:AddPermission
  - lambda:CreateFunction

--- Simulating IAM Permissions ---
  Principal ARN for Simulation: arn:aws:iam::123456789012:user/sufficient-permissions-user

  Simulation Results:
    [PASS] Action: iam:AttachRolePolicy, Resource: *
    [PASS] Action: iam:CreateRole, Resource: *
    [PASS] Action: iam:PassRole, Resource: *
    [PASS] Action: iam:PutRolePolicy, Resource: *
    [PASS] Action: iam:TagRole, Resource: *
    [PASS] Action: lambda:AddPermission, Resource: *
    [PASS] Action: lambda:CreateFunction, Resource: *

--- Pre-flight Check Summary ---
[PASS] Prerequisite checks passed or no prerequisites to check.
[PASS] IAM permission simulation indicates all permissions are present.

Pre-flight checks completed successfully.
```

### 03_lambda_function - Insufficient Permissions

- **Principal ARN:** arn:aws:iam::123456789012:user/insufficient-permissions-user
- **Command:** `python3 ./mock_cc_preflight.py --template-file ../test_cfts/03_lambda_function.yml --deploying-principal-arn arn:aws:iam::123456789012:user/insufficient-permissions-user --region us-east-1 --parameters EnvironmentType=dev`
- **Exit Code:** 1 (Expected: 1)
- **Result:** PASS

**Output:**

```

Parsing template: ../test_cfts/03_lambda_function.yml...
Template description: Test CFT for Lambda Function resource type. This template tests the pre-flight check script's ability to: 1. Detect Lambda function creation 2. Handle IAM role references and PassRole permissions 3. Process environment variables 4. Identify required Lambda actions (lambda:CreateFunction, lambda:TagResource)

Number of resources: 3
Resources: LambdaExecutionRole, TestLambdaFunction, LambdaPermission
Resource types: AWS::IAM::Role, AWS::Lambda::Function, AWS::Lambda::Permission

Required actions: 7
  - iam:AttachRolePolicy
  - iam:CreateRole
  - iam:PassRole
  - iam:PutRolePolicy
  - iam:TagRole
  - lambda:AddPermission
  - lambda:CreateFunction

--- Simulating IAM Permissions ---
  Principal ARN for Simulation: arn:aws:iam::123456789012:user/insufficient-permissions-user

  Simulation Results:
    [PASS] Action: iam:AttachRolePolicy, Resource: *
    [PASS] Action: iam:CreateRole, Resource: *
    [PASS] Action: iam:PassRole, Resource: *
    [PASS] Action: iam:PutRolePolicy, Resource: *
    [PASS] Action: iam:TagRole, Resource: *
    [PASS] Action: lambda:AddPermission, Resource: *
    [PASS] Action: lambda:CreateFunction, Resource: *

--- Pre-flight Check Summary ---
[PASS] Prerequisite checks passed or no prerequisites to check.
[FAIL] IAM permission simulation indicates missing permissions.
        Review the simulation details above for denied actions.

Pre-flight checks identified issues. Review failures before deploying.
```

## IAM Policies Used

### 01_iam_role - Sufficient Permissions

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "iam:CreateRole",
        "iam:DeleteRole",
        "iam:TagRole",
        "iam:UntagRole",
        "iam:AttachRolePolicy",
        "iam:DetachRolePolicy",
        "iam:PutRolePolicy",
        "iam:DeleteRolePolicy"
      ],
      "Resource": "arn:aws:iam::*:role/TestPreflight-Role"
    },
    {
      "Effect": "Allow",
      "Action": [
        "iam:GetRole"
      ],
      "Resource": "*"
    }
  ]
}```

### 01_iam_role - Insufficient Permissions

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "iam:CreateRole",
        "iam:TagRole"
      ],
      "Resource": "arn:aws:iam::*:role/TestPreflight-Role"
    },
    {
      "Effect": "Allow",
      "Action": [
        "iam:GetRole"
      ],
      "Resource": "*"
    }
  ]
}```

### 02_s3_bucket - Sufficient Permissions

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:CreateBucket",
        "s3:DeleteBucket",
        "s3:PutBucketTagging",
        "s3:DeleteBucketTagging",
        "s3:PutEncryptionConfiguration",
        "s3:PutLifecycleConfiguration",
        "s3:PutBucketPolicy",
        "s3:DeleteBucketPolicy",
        "s3:PutBucketVersioning",
        "s3:PutAccelerateConfiguration",
        "s3:PutBucketAcl",
        "s3:GetBucketAcl"
      ],
      "Resource": "arn:aws:s3:::test-preflight-bucket-*"
    }
  ]
}```

### 02_s3_bucket - Insufficient Permissions

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:CreateBucket",
        "s3:PutBucketTagging",
        "s3:PutEncryptionConfiguration"
      ],
      "Resource": "arn:aws:s3:::test-preflight-bucket-*"
    }
  ]
}```

### 03_lambda_function - Sufficient Permissions

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "lambda:CreateFunction",
        "lambda:DeleteFunction",
        "lambda:TagResource",
        "lambda:UntagResource",
        "lambda:UpdateFunctionConfiguration",
        "lambda:UpdateFunctionCode",
        "lambda:AddPermission",
        "lambda:RemovePermission"
      ],
      "Resource": "arn:aws:lambda:*:*:function:test-preflight-function-*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "iam:CreateRole",
        "iam:DeleteRole",
        "iam:TagRole",
        "iam:UntagRole",
        "iam:AttachRolePolicy",
        "iam:DetachRolePolicy",
        "iam:PutRolePolicy",
        "iam:DeleteRolePolicy",
        "iam:PassRole"
      ],
      "Resource": "arn:aws:iam::*:role/*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "iam:GetRole"
      ],
      "Resource": "*"
    }
  ]
}```

### 03_lambda_function - Insufficient Permissions

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "lambda:CreateFunction",
        "lambda:TagResource"
      ],
      "Resource": "arn:aws:lambda:*:*:function:test-preflight-function-*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "iam:CreateRole",
        "iam:TagRole",
        "iam:AttachRolePolicy"
      ],
      "Resource": "arn:aws:iam::*:role/*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "iam:GetRole"
      ],
      "Resource": "*"
    }
  ]
}```

