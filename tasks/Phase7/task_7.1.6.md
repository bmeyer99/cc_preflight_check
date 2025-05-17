# Task Status (DO NOT DELETE)
- **ID**: 7.1.6
- **Title**: Enhance CFT Permission Checks Based on Cortex Cloud Requirements
- **AssignedTo**: Architect
- **From**: User Request (Task 7.1.5 follow-up)
- **Priority**: High
- **Status**: Completed
## Details
### Requirements:
- Review the current IAM permission checking mechanism for CFT deployments.
- Extract all required AWS permissions for resources deployed by CFTs from the provided `Cortex_Cloud_CSP_Permissions.pdf` document.
- Identify any gaps between currently checked permissions and the permissions documented in the PDF, specifically focusing on permissions needed to *create and manage* resources defined in the CFT.
- Develop a plan to update the permission checking logic to include all necessary permissions for deployed resources, ensuring these are simulated against the deploying principal.
### Acceptance Criteria (AC):
- A comprehensive list of AWS permissions required by Cortex Cloud (as per the PDF) is documented. (Completed)
- A list of missing permissions/mis-categorized permissions in the current preflight check is identified. (Completed - primary issue is mis-categorization)
- A detailed plan for updating the preflight check mechanism is created and ready for review. (Completed)
## Planning
- **Dependencies**: None
- **Effort**: Medium
- **Start Date**: 2025-05-17 02:13
- **End Date**: TBD
## Analysis Summary:
The current preflight check mechanism in `template_analyzer.py` distinguishes between `deploying_principal_actions` (simulated) and `resource_actions` (not simulated against the deploying principal). Permissions from `RESOURCE_ACTION_MAP` (like `s3:CreateBucket`) needed to *create* resources defined in a CFT are incorrectly added to `resource_actions` instead of `deploying_principal_actions`. This means they are not being checked against the deploying principal. The `Cortex_Cloud_CSP_Permissions.pdf` lists numerous permissions, some of which are for resource creation/management that CloudFormation would need.

## Proposed Update Plan:

1.  **Modify `template_analyzer.py` Logic:**
    *   In `parse_template_and_collect_actions`, ensure that actions from `RESOURCE_ACTION_MAP` required for CloudFormation to *create and manage* resources defined in the template are added to the `deploying_principal_actions` set. This primarily involves re-categorizing how `generic_actions` and relevant `property_actions` are assigned for newly created resources.
    *   Re-evaluate the purpose and population of the `resource_actions` set.

2.  **Review and Enhance `RESOURCE_ACTION_MAP` in `resource_map.py`:**
    *   Compare the AWS permissions extracted from `Cortex_Cloud_CSP_Permissions.pdf` against the `RESOURCE_ACTION_MAP`.
    *   Verify coverage for relevant Cortex Cloud resource types (EC2, RDS, S3, KMS, ECR, SQS, etc.).
    *   Ensure `generic_actions` (and/or `operation_actions.Create`) in `RESOURCE_ACTION_MAP` include necessary creation, modification, and tagging permissions that CloudFormation would require, aligning with the types of permissions Cortex Cloud interacts with post-deployment.
    *   Carefully consider how to handle very broad managed policies (`ReadOnlyAccess`, `SecurityAudit`) mentioned in the PDF; direct inclusion for the deploying principal might be excessive. Focus on specific actions for CFT-defined resources.

3.  **Consider Granularity (Generic vs. Operation-Specific Actions):**
    *   Evaluate if using `operation_actions.Create` from `RESOURCE_ACTION_MAP` would be more precise than the currently used `generic_actions` for newly created resources. For now, correct categorization of `generic_actions` is the priority.

4.  **Testing Strategy:**
    *   Develop test CFTs defining resources relevant to Cortex Cloud services.
    *   Verify the modified tool correctly identifies and simulates the necessary creation/management permissions against the deploying principal.

## Documentation
### Outcome/Summary:
- Identified that current preflight checks mis-categorize creation permissions, leading to them not being simulated for the deploying principal.
- Extracted relevant AWS permissions from the `Cortex_Cloud_CSP_Permissions.pdf`.
- Modified `template_analyzer.py` to correctly categorize resource creation actions as deploying principal actions.
- Enhanced `resource_map.py` to include missing resource types and permissions required by Cortex Cloud.
- Created a test CloudFormation template (`test_cfts/cortex_cloud_resources.yml`) to verify the changes.
- Fixed an issue in `iam_simulator.py` where actions were being simulated against all resource ARNs instead of only service-relevant ARNs, resulting in incorrect IAM policy generation.

The changes ensure that all permissions required to create and manage resources defined in a CloudFormation template are now correctly simulated against the deploying principal, including those needed for Cortex Cloud resources. Additionally, the generated IAM policies are now more accurate and concise, only granting permissions to the appropriate resources.
### Issues/Blockers:
- None

### Implementation Details:
1. **Changes to `template_analyzer.py`**:
   - Modified the logic to add actions for resources being created by the template to `deploying_principal_actions` instead of `resource_actions`.
   - Updated the handling of property actions and tag actions to ensure they're also added to `deploying_principal_actions`.
   - Added explanatory logging to clarify the change in behavior.

2. **Enhancements to `resource_map.py`**:
   - Added EC2 snapshot-related resources and permissions for Cortex ADS.
   - Added RDS snapshot-related resources and permissions for Cortex DSPM.
   - Added ECR repository resources and permissions for Cortex Registry Scan.
   - Added S3 object-level permissions for Cortex DSPM and Log Collection.

3. **Test CloudFormation Template**:
   - Created `test_cfts/cortex_cloud_resources.yml` with resources that would be used by Cortex Cloud.
   - Included EC2 snapshots, RDS snapshots, ECR repositories, and S3 buckets with appropriate tags.

4. **Fixes to `iam_simulator.py`**:
   - Added a helper function `get_relevant_resource_arns` that filters resource ARNs based on the service of the action.
   - Modified the main simulation loop to use this helper function instead of using all resource ARNs for every action.
   - Added special handling for global actions like `ecr:GetAuthorizationToken` that should use "*" as the resource.
   - Improved logging to show which resources are being used for each action.
### Files:
- [`template_analyzer.py`](template_analyzer.py) - Modified to correctly categorize resource creation actions
- [`resource_map.py`](resource_map.py) - Enhanced with additional resource types and permissions
- [`iam_simulator.py`](iam_simulator.py) - Fixed to correctly filter resource ARNs for each action
- [`test_cfts/cortex_cloud_resources.yml`](test_cfts/cortex_cloud_resources.yml) - Test template with Cortex Cloud resources
- [`.roo/Cortex_Cloud_CSP_Permissions.pdf`](.roo/Cortex_Cloud_CSP_Permissions.pdf) - Reference document for permissions
- [`tasks/Phase7/task_7.1.6.md`](tasks/Phase7/task_7.1.6.md) - Task documentation