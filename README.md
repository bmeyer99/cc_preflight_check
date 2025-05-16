# AWS CloudFormation Pre-flight Check Script for Cortex XDR Template

**README Version:** 2.0
**Based on Script Version:** (Corresponds to the Python script generated on May 16, 2025)
**Current Date:** May 16, 2025

## 1. Overview

This Python script (`cfn_preflight_check.py`) serves as a **pre-flight check mechanism** designed to be executed *before* deploying the Cortex XDR AWS CloudFormation template (specifically, the template like `connectors_aws_cf-d33f925f6195475daf212fdc8b1919e2-1747407759.yml`, hereafter "the Cfn template"). Its core function is to proactively identify potential IAM permission insufficiencies and missing prerequisite resources. By doing so, it aims to significantly reduce the likelihood of CloudFormation stack deployment failures, leading to smoother and more predictable infrastructure provisioning.

The script **dynamically analyzes** the provided Cfn template to understand what AWS resources it intends to create or modify. It then simulates whether a specified IAM principal (the one designated to deploy the Cfn stack) possesses the necessary permissions for these operations.

**Important Note:** This script provides a foundational framework. While it strives for comprehensive analysis of the provided Cfn template, accurately simulating all IAM permissions for highly complex CloudFormation templates is an inherently involved task. This script should be viewed as a powerful starting point that can be iteratively enhanced and adapted.

## 2. Purpose

The primary objectives of this pre-flight check script are:

1.  **Permission Verification:** To simulate and verify that the IAM user/role intending to deploy the CloudFormation stack (the "deploying principal") possesses the required permissions to create, configure, and manage all AWS resources defined within the Cfn template.
2.  **Prerequisite Validation:** To check for the existence and correct configuration of any external AWS resources that the CloudFormation template explicitly depends upon through its parameters (e.g., an existing IAM role specified in the `OutpostRoleArn` parameter).
3.  **Reduce Deployment Failures:** By proactively identifying potential permission gaps or prerequisite issues, this script aims to minimize unexpected errors during the actual CloudFormation stack deployment process.

## 3. How the Script Works (The Dynamic Analysis Process)

The script's operation is dynamic, meaning its checks are directly driven by the content of the CloudFormation template you provide. Here's a step-by-step breakdown:

1.  **Argument Parsing & Initialization:**
    * Accepts command-line arguments: path to the Cfn template, ARN of the deploying IAM principal, target AWS region, and Cfn template parameters.
    * Initializes a Boto3 AWS session (using your local AWS CLI credentials/profile or instance profile) and required AWS clients (IAM, STS).
    * Retrieves the AWS Account ID of the context in which the script is running.

2.  **Parameter Resolution:**
    * Combines template parameter values passed via the command line with default values specified within the Cfn template itself. This resolved set of parameters is used for subsequent steps.

3.  **CloudFormation Template Analysis (`parse_template_and_collect_actions` function):**
    * **Loads and Parses:** Reads and parses the specified CloudFormation YAML template.
    * **Resource Identification:** Iterates through each resource definition in the `Resources` section of the template.
    * **IAM Action Mapping:** For each identified resource, it consults an internal dictionary (`RESOURCE_ACTION_MAP`). This map is crucial and contains:
        * `generic_actions`: A list of common IAM actions (e.g., `iam:CreateRole`, `s3:CreateBucket`) typically required for that AWS resource type.
        * `arn_pattern`: A template string for constructing a resource ARN pattern, used in the IAM simulation. This pattern often includes placeholders like `{accountId}`, `{region}`, and a resource name placeholder.
        * `property_actions`: A sub-dictionary mapping specific CloudFormation resource property names (e.g., `ManagedPolicyArns` for an `AWS::IAM::Role`) to the additional IAM actions they trigger (e.g., `iam:AttachRolePolicy`).
    * **Intrinsic Function Resolution (Basic):** Attempts to resolve simple CloudFormation intrinsic functions within resource properties:
        * `!Ref` to `AWS::AccountId`, `AWS::Region`, and template parameters.
        * Basic `!Sub` string substitutions using these resolved values.
        * Basic `!Join` operations.
        This resolution helps in making the predicted resource names and ARNs (used in simulation) more specific.
    * **Action & ARN Collection:** Aggregates a unique set of all identified IAM actions and a set of predicted resource ARN patterns that the deploying principal would need to interact with.
    * **Prerequisite Identification:** Notes any prerequisite checks required based on resolved template parameters (e.g., the role specified in `OutpostRoleArn`).

4.  **Prerequisite Resource Checks (`check_prerequisites` function):**
    * Validates the existence (and potentially basic configuration) of the identified prerequisite resources. For instance, it verifies that the IAM role specified by the `OutpostRoleArn` parameter exists.

5.  **IAM Permission Simulation (`simulate_iam_permissions` function):**
    * This is the core permission check. It uses the AWS IAM `simulate_principal_policy` API.
    * It queries whether the IAM principal specified by the `--deploying-principal-arn` argument is **allowed** to perform the **collected IAM actions** on the **predicted resource ARN patterns**.
    * `ContextEntries` can be supplied to the simulation (e.g., for `sts:ExternalId` if provided as a parameter) to make the simulation more accurate if the deploying principal's IAM policies or Service Control Policies (SCPs) rely on specific IAM condition context keys.
    * The script then reports which actions are allowed and, more importantly, which are denied.

6.  **Summary Reporting:**
    * Provides a consolidated summary indicating whether all prerequisite checks passed and whether all simulated IAM permissions were granted.

## 4. Requirements

* **Python 3.x:** Recommended Python 3.8 or newer.
* **Boto3 and PyYAML Libraries:**
    ```bash
    pip install boto3 pyyaml
    ```
* **AWS Credentials for Script Execution:**
    * The IAM identity (user or role) that *runs this pre-flight check script* (i.e., your local AWS CLI configured identity or role) needs permissions for:
        * `iam:SimulatePrincipalPolicy` (essential for the permission checks).
        * `sts:GetCallerIdentity` (to determine the AWS account ID for ARN construction).
        * Permissions to describe any prerequisite resources defined in the template and checked by the script (e.g., `iam:GetRole` to verify the role specified in the `OutpostRoleArn` parameter).
* **CloudFormation Template File:** The target Cortex XDR CloudFormation YAML file (e.g., `connectors_aws_cf-d33f925f6195475daf212fdc8b1919e2-1747407759.yml`) must be accessible by the script.
* **Deploying Principal ARN:** You **must** provide the ARN of the IAM user or role that *will actually be used to execute the CloudFormation stack deployment*. The script simulates permissions *for this specified principal*.

## 5. Script Parameters and Justification

The script uses several command-line arguments. Understanding why each is needed is key to effective use:

* `--template-file` (Required)
    * **Why:** This is the primary input. The script needs to read and parse this file to understand *what* AWS resources (IAM roles, S3 buckets, etc.) the CloudFormation template intends to create or modify. Without it, the script cannot determine what permissions to check.

* `--deploying-principal-arn` (Required)
    * **Why:** This specifies *whose* permissions the script should simulate. This is the ARN of the IAM user or role that you plan to use when running `aws cloudformation create-stack` (or update-stack).
    * **Distinction from Script Execution Credentials:** The IAM identity running *this Python script* might be different from the identity deploying the Cfn stack. For example:
        * A security team member (with broader permissions like `iam:SimulatePrincipalPolicy`) might run this script to audit the permissions of a dedicated, less-privileged CloudFormation deployment role.
        * In CI/CD pipelines, the role running the check script might be different from the role deploying the infrastructure.
        This separation allows for flexible permission auditing and adherence to the principle of least privilege.

* `--region` (Required)
    * **Why:** Many AWS resource ARNs are region-specific (e.g., `arn:aws:lambda:us-east-1:...`). The script needs the target deployment region to:
        * Construct more accurate potential ARNs for resources that will be created.
        * Ensure Boto3 clients target the correct regional AWS service endpoints for any API calls (like prerequisite checks).

* `--parameters "Key1=Value1" "Key2=Value2" ...` (Optional, but often necessary)
    * **Why:** These are the parameters you would pass to the CloudFormation stack during its creation or update. The script needs them because:
        * **Prerequisite Identification:** Some parameters (like `OutpostRoleArn` in the Cfn template) point to existing AWS resources. The script uses the provided parameter value to know which specific prerequisite to check.
        * **Resource Naming & Configuration:** Other parameters (e.g., `CortexPlatformRoleName`, `ExternalID`) influence the names, ARNs, or configurations (like IAM Role trust policies or inline policy conditions) of the resources CloudFormation will create. Providing these helps the script:
            * Construct more specific (less wildcarded) ARNs for the IAM simulation.
            * Supply relevant `ContextEntries` (like `sts:ExternalId`) to the IAM simulation if these parameters are used in IAM policy condition keys.
        * **Accuracy of Analysis:** Without these parameters, the script would have to rely solely on default values from the template (if present) or make broader guesses, potentially reducing the accuracy of the pre-flight check.

* `--profile` (Optional)
    * **Why:** If you use named profiles in your AWS CLI configuration, this allows you to specify which profile's credentials the script should use for its own AWS API calls (like `iam:SimulatePrincipalPolicy` and `sts:GetCallerIdentity`).

## 6. How to Run

1.  **Save the Script:** Save the Python code as `cfn_preflight_check.py`.
2.  **Ensure Requirements:** Install Python, `boto3`, and `pyyaml`. Configure AWS credentials for the IAM entity that will *run this script* (ensure it has the necessary permissions listed in Section 4).
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
    * `./connectors_aws_cf-...yml`: Adjust the path to your Cfn template file if it's different.
    * `YOUR_DEPLOYING_ACCOUNT_ID:role/YourCfnDeploymentRole`: Use the **actual ARN** of the principal that will deploy the Cfn stack.
    * `us-east-1`: Set your target AWS deployment region.
    * Adjust other `--parameters` values as necessary to match your intended Cfn stack deployment.

## 7. Key Script Sections & How to Extend

This script is designed for extensibility. Understanding its core components is key to enhancing its capabilities:

* **`RESOURCE_ACTION_MAP` (Global Dictionary):**
    * **The Engine of Permission Mapping.** This dictionary is the most critical component for the script's accuracy regarding IAM checks.
    * **Structure:** Maps CloudFormation resource types (e.g., `AWS::IAM::Role`) to:
        * `generic_actions`: A list of common IAM actions (e.g., `iam:CreateRole`) for that resource.
        * `arn_pattern`: A template string for constructing resource ARN patterns for simulation. Uses placeholders like `{accountId}`, `{region}`, `{roleName}`.
        * `property_actions`: A sub-dictionary. Maps specific CloudFormation resource *property names* (e.g., `ManagedPolicyArns` for an `AWS::IAM::Role`) to the *additional IAM actions* those properties trigger (e.g., `iam:AttachRolePolicy`).
    * **How to Extend:**
        1.  **Identify Missing Resources/Actions:** If the script reports "Warning: No specific IAM action mapping found..." for a resource type in your template, or if a deployment fails due to a permission not checked by the script, that's a cue to update this map.
        2.  **Consult AWS Documentation:** For the specific AWS service and resource type (e.g., "IAM permissions for creating S3 buckets with CloudFormation"), find the precise IAM actions required for each CloudFormation property you use.
        3.  **Update `generic_actions`:** Add general create/delete/tag actions.
        4.  **Define/Refine `arn_pattern`:** Make it as specific as possible while still being usable for pre-flight (non-existent) resources.
        5.  **Populate `property_actions`:** This is key for detailed accuracy. If setting `BucketEncryption` on an `AWS::S3::Bucket` requires `s3:PutEncryptionConfiguration`, add that mapping. Pay special attention to `iam:PassRole` permissions if roles are being passed to services (e.g., a Lambda function's `Role` property).

* **`resolve_value()` (Function):**
    * Handles basic CloudFormation intrinsic function resolution (`!Ref` to parameters/globals, basic `!Sub`, basic `!Join`).
    * **How to Extend:**
        * Improve `!Ref` to handle references to other logical resources *within the template*. This is complex as it requires predicting the ARN or relevant identifier of a not-yet-created resource.
        * Enhance `!Sub` to fully support its list form (`Fn::Sub: [String, { Var1Name: Var1Value, ... }]`) and more complex variable substitutions.
        * Implement `!GetAtt` (highly challenging for pre-flight, as attributes of non-existent resources are unknown; might involve returning placeholders or making educated guesses based on resource type).
        * Add support for other intrinsic functions (`!ImportValue`, `!Select`, `!Split`, etc.) if your templates use them extensively and they influence permissions or ARNs.

* **`parse_template_and_collect_actions()` (Function):**
    * This function iterates through resources defined in the Cfn template.
    * **Resource Naming for ARN Patterns:** It attempts to derive resource names from common properties (`RoleName`, `BucketName`, etc.) or uses the resource's logical ID as a fallback. Enhancing the logic to more accurately predict the final physical name (where possible, as CFN often adds unique suffixes) can improve ARN specificity for simulation.
    * **Tagging Permissions:** The script includes a generic attempt to add `service:TagResource`. Ideally, this should be made specific per resource type within `RESOURCE_ACTION_MAP` (e.g., `s3:PutBucketTagging`, `iam:TagRole`).
    * **How to Extend:** Refine how resource names are extracted or predicted. If a resource type has a very specific naming convention when created by CloudFormation without an explicit name, try to incorporate that into the ARN pattern generation.

* **`check_prerequisites()` (Function):**
    * Currently focuses on `iam_role_exists` for the `OutpostRoleArn` parameter.
    * **How to Extend:** Add new check types (e.g., `s3_bucket_exists`, `kms_key_exists`, `vpc_exists`) and the corresponding Boto3 calls if your templates depend on other kinds of pre-existing resources identified by parameters.

* **`simulate_iam_permissions()` (Function):**
    * Constructs the input for the `iam_client.simulate_principal_policy()` API call.
    * **ContextEntries:** Currently includes `sts:ExternalId`. If your IAM policies or Service Control Policies (SCPs) rely heavily on other IAM condition context keys (e.g., `aws:RequestTag/*`, `aws:SourceIp`, `ec2:ResourceTag/...`, specific service condition keys), add them to the `context_entries` list for more accurate simulation. The values for these context keys might need to be passed as additional command-line parameters to the script or intelligently derived.
    * **API Limits & Batching:** The `simulate_principal_policy` API has limits on the number of actions, resource ARNs, and context entries per call. For extremely large CloudFormation templates generating many actions/resources, the script might need to be enhanced to batch these simulation calls.

## 8. Information from the Cortex XDR Cfn Template (`connectors_aws_cf-...yml`) Relevant to This Script

Understanding key aspects of the target CloudFormation template helps in interpreting the script's behavior and potential areas for refinement:

* **Key Parameters Influencing Checks:**
    * `OrganizationalUnitId`: Primarily for `AWS::CloudFormation::StackSet`'s `DeploymentTargets`. Less directly related to the deploying principal's IAM permissions in the *management account* for basic resource creation, but vital for StackSet operation.
    * `ExternalID`: Directly used in `sts:ExternalId` conditions within `AssumeRolePolicyDocument` for several IAM roles created by the template. The script includes this in `ContextEntries` for the IAM simulation.
    * `OutpostRoleArn`: A critical prerequisite. The script checks its existence. This ARN is used as a `Principal` in the `AssumeRolePolicyDocument` of the `CortexPlatformRole`.
    * `CortexPlatformRoleName`, `CortexPlatformScannerRoleName`: These define the names of key IAM roles to be created. The script uses these (or their defaults if not provided via `--parameters`) to construct more specific ARN patterns for simulation.
    * `Audience`, `CollectorServiceAccountId`: Used in the `AssumeRolePolicyDocument` of the `CloudTrailReadRole`. These affect the trust policy of the created role.
    * `OutpostAccountId`, `MTKmsAccount`: These Account IDs appear within conditions in inline IAM policies (e.g., `Cortex-Agentless-Policy` conditions like `ec2:Add/userId` or KMS key resource ARNs like `arn:aws:kms:*:${MTKmsAccount}:key/*`). While the script doesn't deeply parse inline policy *content* to extract further actions for the *deploying principal*, understanding these helps interpret the template's requirements.

* **Primary Resource Types & General IAM Actions:**
    * `AWS::IAM::Role`: Requires `iam:CreateRole`, `iam:TagRole`. If `ManagedPolicyArns` are present, `iam:AttachRolePolicy`. If `Policies` (inline) are present, `iam:PutRolePolicy`. If `Role` is passed to Lambda (e.g., for `CortexTemplateCustomLambdaFunction`'s execution role), `iam:PassRole` on the execution role ARN.
    * `AWS::CloudFormation::StackSet`: `cloudformation:CreateStackSet`, `iam:PassRole` (for `AdministrationRoleARN` and `ExecutionRoleName` if explicitly defined; this template uses `SERVICE_MANAGED` permissions, which implies CloudFormation service principals handle cross-account actions based on OU trust).
    * `AWS::Lambda::Function`: `lambda:CreateFunction`, `lambda:TagResource`, `iam:PassRole` (for the function's specified execution role).
    * `AWS::KMS::Key`: `kms:CreateKey`, `kms:TagResource`, `kms:PutKeyPolicy` (as key policy is usually defined at creation).
    * `AWS::S3::Bucket`: `s3:CreateBucket`, `s3:PutEncryptionConfiguration`, `s3:PutLifecycleConfiguration`, `s3:PutBucketTagging`.
    * `AWS::S3::BucketPolicy`: `s3:PutBucketPolicy` (action on the bucket).
    * `AWS::SQS::Queue`: `sqs:CreateQueue`, `sqs:SetQueueAttributes` (for policies/attributes), `sqs:TagQueue`.
    * `AWS::SNS::Topic`: `sns:CreateTopic`, `sns:SetTopicAttributes`, `sns:TagResource`.
    * `AWS::SNS::Subscription`: `sns:Subscribe`. Note: The endpoint (e.g., SQS queue) also needs a policy allowing SNS to publish to it.
    * `AWS::CloudTrail::Trail`: `cloudtrail:CreateTrail`, `cloudtrail:TagResource`. Also requires permissions for associated resources: `s3:PutObject` (for the S3 bucket), `s3:GetBucketAcl` (CloudTrail needs to verify bucket), `kms:GenerateDataKey*` (for the specified KMS key).

* **Use of Intrinsic Functions and Naming:**
    * The template makes extensive use of `!Ref` (e.g., `!Ref 'AWS::AccountId'`, `!Ref 'ExternalID'`).
    * `!Sub` is frequently used for constructing resource names and ARNs (e.g., `!Sub 'cortex-cloudtrail-logs-${AWS::AccountId}-m-o-1008133351020'`). The script's basic resolution of these is vital.
    * `!GetAtt` is used (e.g., `!GetAtt 'CloudTrailLogsQueue.Arn'`). Accurate pre-flight resolution of `!GetAtt` for attributes of not-yet-created resources is highly complex; the script currently returns a placeholder string for these.
    * `!Join` is also present. The script performs basic resolution for this.

* **Custom Resources (`Custom::PublishRoleDetail`, `Custom::EmptyBucketDetails`):**
    * The pre-flight check will focus on the deploying principal's permissions to create the backing `AWS::Lambda::Function` and its associated `AWS::IAM::Role` (the execution role).
    * It does **not** validate the internal logic of these Lambda functions (e.g., the external HTTP PUT request made by `CortexTemplateCustomLambdaFunction`).

## 9. Caveats and Limitations

* **IAM Simulation Accuracy:**
    * AWS IAM `simulate_principal_policy` is a powerful diagnostic tool but may not perfectly replicate every real-world authorization scenario, especially those involving complex IAM condition keys, resource-based policies on resources that are not yet created, or nuanced service-specific behaviors during CloudFormation deployment.
    * **Wildcard ARNs:** For resources that do not yet exist, the script often uses wildcard ARNs (e.g., `arn:aws:s3:::*` or `arn:aws:iam::123456789012:role/*`) in the simulation. An "allowed" decision with a wildcard means the principal can perform the action on *any* resource of that type. This is less precise than simulating against a specific, fully-formed ARN. If the principal's actual IAM policies are narrowly scoped to specific resource names or paths that CloudFormation would generate, a wildcard simulation might incorrectly report "allowed," while the actual deployment could fail.
* **Incomplete IAM Action Mapping (`RESOURCE_ACTION_MAP`):** The provided map is a strong starting point tailored to the Cfn template but may not cover every IAM permission required for every possible property or configuration of every AWS resource. AWS IAM is extensive, and new features or properties can introduce new permission requirements. Continuous refinement of this map is key to improving accuracy.
* **Limited Intrinsic Function Resolution:** The script currently handles only basic `!Ref` (to parameters and AWS pseudo-parameters), `!Sub` (simple substitutions), and `!Join`. More complex CloudFormation template logic using other intrinsic functions (`!GetAtt` for non-existent resources, `!ImportValue`, `!Select`, `!Split`, etc.) or deeply nested functions may not be fully resolved. This can affect the accuracy of the predicted resource ARNs and, consequently, the IAM simulation.
* **CloudFormation `Condition` Statements:** The script does not evaluate `Condition` statements within the CloudFormation template. It generally assumes all resources defined in the `Resources` section are intended for creation when it gathers IAM actions for simulation.
* **Service Quotas (AWS Limits):** This script **does not** check if your AWS account has sufficient service quotas (e.g., limits on the number of IAM roles, S3 buckets, VPCs, etc.) for the resources intended to be deployed. Quota issues can cause deployment failures unrelated to IAM permissions.
* **`AWS::CloudFormation::StackSet` Instance Permissions:** For the `AWS::CloudFormation::StackSet` resource, especially when using `PermissionModel: SERVICE_MANAGED` (as in the Cfn template), this script primarily checks the deploying principal's permissions to create and manage the StackSet *itself* in the management account (e.g., `cloudformation:CreateStackSet`). The permissions required by the *StackSet's execution role* (which CloudFormation typically creates or you specify) to provision/manage stack *instances* in the target accounts/OUs are a separate, more complex validation scope that this script does not currently cover in depth.
* **Custom Resource Internal Logic:** The script checks permissions to create the custom resource's backing Lambda function and its IAM execution role. It **cannot** validate the internal logic or actions performed by the Lambda function code itself (e.g., its ability to make external HTTP calls, as seen with `CortexTemplateCustomLambdaFunction` in the Cfn template).
* **Dynamic Naming by CloudFormation:** CloudFormation often appends unique suffixes to resource names if a name isn't explicitly provided. Predicting these exact physical IDs pre-flight is generally impossible. The script uses logical IDs or patterns as placeholders.
* **Script Idempotency (Read-Only):** The script itself is designed to be read-only and makes no changes to your AWS environment.

## 10. Disclaimer

This script is provided "as-is" without any warranties, for educational and pre-flight diagnostic purposes. It is a tool to aid in identifying potential issues and is not a replacement for thorough testing and understanding of AWS IAM and CloudFormation. Always test CloudFormation templates and associated permissions in a non-production environment first. The IAM entity running this script, and the principal whose permissions are being simulated, should adhere to the principle of least privilege. The authors or contributors are not responsible for any issues, damages, or incorrect conclusions arising from the use or interpretation of this script or its results. Users should be aware of its limitations and use their judgment when interpreting its output.
