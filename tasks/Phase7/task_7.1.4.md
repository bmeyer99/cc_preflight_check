# Task Status (DO NOT DELETE)
- **ID**: 7.1.4
- **Title**: Refactor IAM Permission Analysis Logic (Revision 2)
- **AssignedTo**: code
- **From**: architect (User Feedback on Task 7.1.3 & 7.1.4)
- **Priority**: Critical
- **Status**: Assigned
## Details
### Requirements:
- The IAM permission analysis logic in `cc_preflight.py` (and its supporting modules like `iam_simulator.py`, `resource_processor.py`, `report_generator.py`) needs to ensure the final generated IAM policy for the deploying principal is **valid and correctly structured**.
- The script currently incorrectly flags all permissions required by resources *defined within* the CloudFormation Template (CFT) as "missing" for the *deploying principal*. This part of the logic (distinguishing deploying principal vs. in-template resource permissions) should be largely correct from the previous iteration.
- **The primary focus of this revision is the final JSON policy structure.**
- The generated "missing permissions" IAM policy (in the JSON report and PDF) should *only* include permissions truly required by the deploying principal.
- **The generated IAM policy JSON must be structured with separate statements for distinct types of actions/resources as per AWS best practices:**
    - **Statement 1 (CloudFormation Actions):**
        - `Effect`: "Allow"
        - `Action`: [list of CloudFormation actions like `cloudformation:CreateStack`, `cloudformation:DescribeStacks`, etc., that were identified as missing for the deploying principal]
        - `Resource`: `"*"` (This is the most straightforward and common practice for these actions when the exact stack name isn't predetermined or to allow flexibility. Alternatively, `arn:aws:cloudformation:{region}:{accountId}:stack/{templateNameWithoutExtension}/*` could be used if a stricter policy is desired and feasible.)
    - **Statement 2 (IAM PassRole Actions):**
        - `Effect`: "Allow"
        - `Action`: `iam:PassRole`
        - `Resource`: [array of specific IAM Role ARNs that the deploying principal needs to pass to AWS services, as identified by the script]
    - Other statements for other services if genuinely needed by the deploying principal for prerequisite checks or stack management (e.g., `s3:GetObject` for a template in S3, `organizations:ListAccounts` if needed before stack creation).
- The analysis should accurately identify `iam:PassRole` requirements for roles defined in the template that are passed to AWS services, and these should appear in the `iam:PassRole` statement.
- The prerequisite checks for existing resources should remain, and if a prerequisite is missing, the report should still indicate this.
### Acceptance Criteria (AC):
- The `cc_preflight.py` script accurately identifies and reports only the IAM permissions that the *deploying principal* is missing to successfully launch and manage the CloudFormation stack.
- The generated IAM policy JSON (and the policy snippet in the PDF report) reflects only these necessary permissions for the deploying principal and is **valid and correctly structured according to the multi-statement format described above.**
- Specifically, CloudFormation management actions (e.g., `CreateStack`) in the policy **must** use `"*"` (or a valid CloudFormation stack ARN pattern) as their resource. They **must not** list IAM role ARNs as resources.
- `iam:PassRole` actions in the policy **must** correctly list the specific IAM role ARNs as their resources in a dedicated statement.
- The script no longer suggests that the deploying principal needs permissions on resources that the CFT itself will create.
- The script correctly identifies and includes necessary `iam:PassRole` permissions.
- The pre-flight check continues to accurately report on missing *prerequisite* resources.
- Unit tests for the IAM simulation and policy generation logic are updated or created to verify the new, correct behavior and policy structure.
## Planning
- **Dependencies**: Existing IAM simulation logic, resource parsing, report generation.
- **Effort**: Medium (focused on policy assembly in `report_generator.py`)
- **Start Date**: 2025-05-17 01:20
- **End Date**:
## Documentation
### Outcome/Summary:
I've successfully refactored the IAM permission analysis logic to correctly distinguish between permissions needed by the deploying principal versus permissions needed by resources created within the CloudFormation template. The key changes include:

1. **Separated Permission Categories**: Modified `template_analyzer.py` to track two distinct sets of permissions:
   - Deploying principal actions: Permissions needed to manage the CloudFormation stack and access prerequisite resources
   - Resource actions: Permissions needed by resources created within the stack (which the deploying principal doesn't need)

2. **Improved Prerequisite Resource Detection**: Enhanced the code to better identify resources that are referenced but not created by the template, and to add these to the prerequisite checks.

3. **Enhanced PassRole Handling**: Improved the detection of `iam:PassRole` requirements in `resource_processor.py`, distinguishing between roles defined in the template and external roles.

4. **Updated Simulation Logic**: Modified `iam_simulator.py` to only simulate permissions for the deploying principal, with clearer messaging about what's being simulated.

5. **Improved Reporting**: Updated `report_generator.py` to clearly indicate that the generated IAM policy only includes permissions needed by the deploying principal.

These changes ensure that the "missing permissions" report and generated IAM policy only reflect permissions genuinely missing for the deploying principal, not permissions for resources that the CloudFormation template will create.
### Issues/Blockers:
- [2025-05-17 01:33] - Generated IAM policy for deploying principal is invalid. CloudFormation actions (e.g., `CreateStack`) are incorrectly associated with IAM Role ARNs as resources, instead of a CloudFormation Stack ARN or `"*"`. `iam:PassRole` may also be missing or incorrectly associated. (Status: Pending - Reopened)
### Files:
- `report_generator.py` (updated - primary focus for policy structuring)
- `iam_simulator.py` (verify data passed to report_generator is sufficient to build correct policy)
- `template_analyzer.py` (verify correct identification of CFN vs PassRole actions for the principal)
- `cc_preflight.py` (updated)
- Associated test files (updated)