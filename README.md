# AWS CloudFormation Pre-flight Check Script for Cortex XDR Template

## 1. Overview

This Python script (`cfn_preflight_check.py`) is designed to perform **pre-flight checks** *before* deploying the Cortex XDR AWS CloudFormation template (referred to as `connectors_aws_cf-d33f925f6195475daf212fdc8b1919e2-1747407759.yml`, hereafter "the Cfn template"). Its primary purpose is to identify potential IAM permission issues and missing prerequisites, thereby reducing CloudFormation stack deployment failures.

The script analyzes the Cfn template, attempts to determine the necessary IAM permissions for creating the defined resources, and then simulates whether a specified IAM principal (the one that would deploy the stack) possesses these permissions. It also checks for the existence of key prerequisite resources defined as parameters in the Cfn template.

**Current Date of Generation:** May 16, 2025

**Important Note:** This script provides a foundational framework. While it aims to be as comprehensive as possible for the provided Cfn template, accurately simulating all IAM permissions for complex CloudFormation templates is a highly involved task. Consider this script a powerful starting point that can be iteratively improved.

## 2. Purpose

The main goals of this pre-flight check script are:

1.  **Permission Verification:** To simulate and verify that the IAM user/role intending to deploy the CloudFormation stack possesses the required permissions to create and configure all the AWS resources defined within the template.
2.  **Prerequisite Validation:** To check for the existence and correct configuration of any external AWS resources that the CloudFormation template relies upon (e.g., an existing IAM role referenced in the `OutpostRoleArn` parameter that will be part of a trust policy).
3.  **Reduce Deployment Failures:** By identifying potential permission issues or missing prerequisites beforehand, this script aims to reduce the likelihood of CloudFormation stack deployment failures.

## 3. How the Script Works

The script executes the following main steps:

1.  **Argument Parsing:** Accepts command-line arguments such as the path to the Cfn template, the ARN of the IAM principal that will deploy the stack, the target AWS region, and any Cfn template parameters.
2.  **AWS Session Initialization:** Sets up a Boto3 session using provided AWS CLI profile (if any) and region.
3.  **Account ID Retrieval:** Fetches the AWS Account ID of the current context using STS.
4.  **Parameter Resolution:** Combines CLI-provided parameters with default values from the Cfn template.
5.  **Template Parsing (`parse_template_and_collect_actions`):**
    * Loads and parses the specified CloudFormation YAML template.
    * Iterates through each resource defined in the `Resources` section.
    * For each resource, it consults the `RESOURCE_ACTION_MAP` (a core dictionary within the script) to find:
        * A list of generic IAM actions typically required for that resource type.
        * An ARN pattern used for the simulation.
        * Specific actions triggered by certain resource properties (e.g., `iam:PassRole` for a Lambda's `Role` property).
    * It attempts to resolve simple CloudFormation intrinsic functions (`!Ref` to parameters/globals, basic `!Sub`) to make ARNs and resource names more specific for simulation.
    * Collects a unique set of IAM actions and a set of potential resource ARNs for the simulation.
    * Identifies prerequisite checks based on template parameters (e.g., the role specified in `OutpostRoleArn`).
6.  **Prerequisite Checks (`check_prerequisites`):**
    * Validates the existence of identified prerequisite resources (currently, checks if the IAM role for `OutpostRoleArn` exists).
7.  **IAM Permission Simulation (`simulate_iam_permissions`):**
    * Uses the AWS IAM `simulate_principal_policy` API call.
    * This API call checks if the `--deploying-principal-arn` is allowed to perform the collected `actions` on the collected `resource_arns`.
    * It can also take `ContextEntries` (e.g., for `sts:ExternalId`) to make the simulation more accurate if policies rely on context keys.
    * Reports which actions are allowed and which are denied.
8.  **Summary Reporting:** Provides a summary of whether prerequisite and permission checks passed or failed.

## 4. Requirements

* **Python 3.x:** (e.g., Python 3.8+)
* **Boto3 and PyYAML Libraries:**
    ```bash
    pip install boto3 pyyaml
    ```
* **AWS Credentials for Running the Script:**
    * The IAM entity (user or role) running *this pre-flight check script* must have permissions to:
        * `iam:SimulatePrincipalPolicy` (or `iam:SimulateCustomPolicy`).
        * `sts:GetCallerIdentity`.
        * Permissions to describe any prerequisite resources being checked (e.g., `iam:GetRole` to verify the role specified in the `OutpostRoleArn` parameter).
* **CloudFormation Template File:** The Cortex XDR CloudFormation YAML file (`connectors_aws_cf-d33f925f6195475daf212fdc8b1919e2-1747407759.yml`) must be accessible by the script.
* **Deploying Principal ARN:** You must provide the ARN of the IAM user or role that *will actually be used to deploy the CloudFormation stack*. The script simulates permissions for this principal.

## 5. How to Run

1.  **Save the Script:** Save the Python code as `cfn_preflight_check.py`.
2.  **Ensure Prerequisites:** Install Python and the required libraries. Configure AWS credentials for the entity that will *run the script*.
3.  **Execute from Terminal:**

    ```bash
    python cfn_preflight_check.py \
        --template-file "./connectors_aws_cf-d33f925f6195475daf212fdc8b1919e2-1747407759.yml" \
        --deploying-principal-arn "arn:aws:iam::YOUR_DEPLOYING_ACCOUNT_ID:role/YourCfnDeploymentRole" \
        --region "us-east-1" \
        --parameters "OutpostRoleArn=arn:aws:iam::650251731026:role/gcp_saas_role" \
                     "ExternalID=d5e1e7e8-58c1-430d-8326-65c5a0d8171c" \
                     "CortexPlatformRoleName=CortexPlatformRole-m-o-1008133351020" \
                     "OrganizationalUnitId=r-xxxxxxxx" \
        # --profile your-aws-cli-profile # Optional: if using a specific AWS CLI profile
    ```

    **Replace placeholders:**
    * `./connectors_aws_cf-...yml`: Adjust path if needed.
    * `YOUR_DEPLOYING_ACCOUNT_ID:role/YourCfnDeploymentRole`: Use the actual ARN of the principal that will deploy the Cfn stack.
    * `us-east-1`: Set your target AWS region.
    * Adjust `--parameters` as necessary. Provide values for parameters that:
        * Point to prerequisite resources.
        * Influence resource names or critical configurations.
        * Do not have defaults in the template and are required.

## 6. Key Script Sections & How to Extend

This script is designed to be extensible. Here are the key areas for understanding and enhancement:

* **`RESOURCE_ACTION_MAP` (Global Dictionary):**
    * **This is the most critical part for accuracy.** It maps CloudFormation resource types (e.g., `AWS::IAM::Role`) to:
        * `generic_actions`: A list of common IAM actions for creating/managing that resource.
        * `arn_pattern`: A string pattern for constructing a resource ARN for simulation. Placeholders like `{accountId}`, `{region}`, `{roleName}` are used.
        * `property_actions`: A dictionary mapping resource property names (e.g., `ManagedPolicyArns` for an IAM Role) to additional IAM actions they trigger.
        * `pass_role_to_services`: (Example, can be expanded) For services that require `iam:PassRole`.
    * **To Extend:**
        * For any new resource type or an existing one with missing actions, add/update its entry in this map.
        * Consult the AWS documentation for the specific service to find the exact IAM permissions needed for each CloudFormation property.
        * Pay close attention to actions like `iam:PassRole`, tagging actions (e.g., `s3:PutBucketTagging` vs. `iam:TagRole`), and policy-setting actions.

* **`resolve_value()` (Function):**
    * Handles basic CloudFormation intrinsic function resolution:
        * `Ref` to `AWS::AccountId`, `AWS::Region`, and template parameters.
        * Basic `Fn::Sub` string substitutions for the above.
        * Basic `Fn::Join`.
    * **To Extend:**
        * Add support for `Ref` to other resources within the template (requires careful handling of how ARNs are predicted).
        * Enhance `Fn::Sub` to support its list form and more complex variable substitutions.
        * Implement `Fn::GetAtt` (challenging for pre-flight, as attributes of non-existent resources are unknown; might return placeholders).
        * Add support for other intrinsic functions (`!ImportValue`, `!Select`, etc.) if present in your templates.

* **`parse_template_and_collect_actions()` (Function):**
    * This function iterates through resources in the Cfn template.
    * **Resource Naming for ARN Patterns:** It attempts to derive resource names from properties like `RoleName`, `BucketName`, etc., or uses the logical ID as a fallback. Improving the specificity of these derived names will make the `resource_arns_for_simulation` more accurate.
    * **Tagging Permissions:** Includes a generic attempt to add `service:TagResource`. This should ideally be made specific per resource type within `RESOURCE_ACTION_MAP`.
    * **To Extend:** Refine how resource names are extracted or predicted for ARN construction, especially for resources with auto-generated names.

* **`check_prerequisites()` (Function):**
    * Currently checks for `iam_role_exists` based on the `OutpostRoleArn` parameter.
    * **To Extend:** Add more check types and logic if your template relies on other kinds of pre-existing resources (e.g., S3 buckets, KMS keys, VPCs) defined by parameters.

* **`simulate_iam_permissions()` (Function):**
    * Constructs the input for `iam_client.simulate_principal_policy()`.
    * **ContextEntries:** Currently includes an example for `sts:ExternalId`. If your IAM policies or SCPs rely heavily on other condition context keys (e.g., `aws:RequestTag/*`, `aws:SourceIp`, specific service conditions), add them to `context_entries` for more accurate simulation. The values for these context keys might need to be passed as parameters to the script.
    * **Batching:** IAM simulation API has limits on the number of actions/resources per call. For very large templates, batching simulation calls might be necessary.

## 7. Information from the Cortex XDR Cfn Template (`connectors_aws_cf-...yml`) relevant to this script:

* **Parameters to Pay Attention To:**
    * `OrganizationalUnitId`: Not directly used for IAM permission checks of the deploying principal in the *management account*, but crucial for the `AWS::CloudFormation::StackSet` resource's `DeploymentTargets`.
    * `ExternalID`: Used in `sts:ExternalId` conditions in `AssumeRolePolicyDocument` for several roles. The script includes this in `ContextEntries` for simulation.
    * `OutpostRoleArn`: A critical prerequisite. The script checks its existence. This ARN is used as a Principal in the `AssumeRolePolicyDocument` of `CortexPlatformRole`.
    * `CortexPlatformRoleName`, `CortexPlatformScannerRoleName`: These define the names of key IAM roles to be created. The script uses these (or defaults) to construct ARN patterns for simulation.
    * `Audience`, `CollectorServiceAccountId`: Used in the `AssumeRolePolicyDocument` of `CloudTrailReadRole`. These affect the trust policy, not directly the deploying principal's permissions to *create* the role, but a very advanced script might try to validate the resulting policy document's syntax.
    * `OutpostAccountId`, `MTKmsAccount`: These Account IDs are used within inline policy conditions (e.g., `ec2:Add/userId`, KMS key resource ARNs). While the script doesn't deeply parse inline policy content for simulation actions, knowing these helps understand the template's intent.

* **Key Resource Types and Actions to Verify:**
    * **`AWS::IAM::Role`:** `iam:CreateRole`, `iam:TagRole`, `iam:PutRolePolicy` (for inline policies), `iam:AttachRolePolicy` (for `ManagedPolicyArns`), `iam:PassRole` (if roles are passed to Lambda, e.g., for `CortexTemplateCustomLambdaFunction`).
    * **`AWS::CloudFormation::StackSet`:** `cloudformation:CreateStackSet`, `iam:PassRole` (for `AdministrationRoleArn` and `ExecutionRoleName` if they were used, though this template uses `SERVICE_MANAGED` which has its own implications).
    * **`AWS::Lambda::Function`:** `lambda:CreateFunction`, `lambda:TagResource`, `iam:PassRole` (for the function's execution role).
    * **`AWS::KMS::Key`:** `kms:CreateKey`, `kms:TagResource`, `kms:PutKeyPolicy`.
    * **`AWS::S3::Bucket`:** `s3:CreateBucket`, `s3:PutEncryptionConfiguration`, `s3:PutLifecycleConfiguration`, `s3:PutBucketTagging`.
    * **`AWS::S3::BucketPolicy`:** `s3:PutBucketPolicy`.
    * **`AWS::SQS::Queue`:** `sqs:CreateQueue`, `sqs:SetQueueAttributes`, `sqs:TagQueue`.
    * **`AWS::SQS::QueuePolicy`:** `sqs:SetQueueAttributes` (policy is an attribute).
    * **`AWS::SNS::Topic`:** `sns:CreateTopic`, `sns:SetTopicAttributes`, `sns:TagResource`.
    * **`AWS::SNS::TopicPolicy`:** `sns:SetTopicAttributes`.
    * **`AWS::SNS::Subscription`:** `sns:Subscribe`.
    * **`AWS::CloudTrail::Trail`:** `cloudtrail:CreateTrail`, `cloudtrail:TagResource`, `s3:PutObject` (for the S3 bucket), `s3:GetBucketPolicy` (for CloudTrail to validate bucket policy), `kms:GenerateDataKey*` (for the KMS key).

* **Intrinsic Functions and Naming:**
    * The template uses `!Ref` extensively (e.g., `!Ref 'AWS::AccountId'`, `!Ref 'ExternalID'`).
    * `!Sub` is used for constructing names and ARNs (e.g., `!Sub 'cortex-cloudtrail-logs-${AWS::AccountId}-m-o-1008133351020'`). The script attempts basic resolution.
    * `!GetAtt` is used (e.g., `!GetAtt 'CloudTrailLogsQueue.Arn'`). Pre-flight resolution of `!GetAtt` is difficult; the script currently returns a placeholder.
    * `!Join` is also used. The script attempts basic resolution.

* **Custom Resources:** The template defines `Custom::PublishRoleDetail` and `Custom::EmptyBucketDetails`. The pre-flight check focuses on permissions to create the backing `AWS::Lambda::Function` and its `AWS::IAM::Role`.

## 8. Caveats and Limitations

* **IAM Simulation is Not Perfect:**
    * AWS IAM `simulate_principal_policy` is a powerful tool but may not replicate every real-world authorization scenario, especially with complex condition keys, resource policies not yet created, or service-specific behaviors.
    * Simulating with wildcard resource ARNs (`*`) (often necessary for not-yet-created resources) can lead to "allowed" decisions that might fail in practice if the principal's actual permissions are scoped to specific resource names or paths that CloudFormation would generate.
* **Incomplete IAM Action Mapping:** The `RESOURCE_ACTION_MAP` in the script is a starting point. It likely does not cover every IAM permission required for every property of every resource in the Cfn template. Thoroughly mapping all actions is a continuous effort.
* **Limited Intrinsic Function Resolution:** The script handles only basic `!Ref`, `!Sub`, and `!Join`. More complex template logic using other functions or nested structures might not be fully resolved, potentially affecting the accuracy of generated ARNs for simulation.
* **CloudFormation Conditions:** The script does not evaluate `Condition` statements in the template. It assumes all defined resources are intended for creation when gathering actions for simulation.
* **Service Quotas (Limits):** This script **does not** check if your AWS account has sufficient service quotas (e.g., number of IAM roles, S3 buckets) for the resources to be deployed.
* **StackSet Instance Permissions:** For `AWS::CloudFormation::StackSet` with `SERVICE_MANAGED` permissions, this script primarily checks the deploying principal's ability to create/manage the StackSet itself in the management account. The permissions needed by the *StackSet execution role* in the target accounts are a separate, more complex validation that this script does not cover.
* **Custom Resource Logic:** The script checks permissions to create the custom resource's backing Lambda and its IAM role. It **cannot** validate the internal logic of the Lambda function (e.g., its ability to make external HTTP calls as seen in `CortexTemplateCustomLambdaFunction`).
* **Dynamic References During Deployment:** CloudFormation often resolves references and generates names dynamically during stack creation. Predicting all these perfectly pre-flight is challenging.
* **Idempotency of the Script:** The script itself is read-only and makes no changes to your AWS environment.

## 9. Disclaimer

This script is provided "as-is" without any warranties, for educational and pre-flight checking purposes. Always test thoroughly in a non-production environment before relying on its results for critical deployments. The IAM entity running this script and the principal being simulated should have appropriate, least-privilege permissions. The authors or contributors are not responsible for any issues, damages, or incorrect conclusions arising from its use or interpretation. Ensure you understand its limitations.
