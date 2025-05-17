# Task Status (DO NOT DELETE)
- **ID**: 6.1.2
- **Title**: Enhance `cc_preflight.py` for Interactive Input & AWS Config Detection
- **AssignedTo**: Cody
- **From**: Task 6.1.1 (User Request)
- **Priority**: High
- **Status**: Completed
## Details
### Requirements:
- Modify `cc_preflight.py` to reduce reliance on command-line arguments by implementing interactive prompts and AWS environment configuration detection.
- The script should prompt for necessary inputs if they are not provided as arguments or cannot be auto-detected.
- Default values for prompts should be intelligently derived from the user's AWS CLI configuration (e.g., `~/.aws/credentials`, `~/.aws/config`) or current AWS session.
- If a CloudFormation template targets an AWS Organization (e.g., via `AWS::CloudFormation::StackSet`), the script should attempt to list available Organizational Units (OUs) and allow the user to select one if the `OrganizationalUnitId` parameter is required but not provided.
- Update in-code comments within `cc_preflight.py` to reflect the new functionality.
- Update the main project [`README.md`](README.md) to document the new interactive features, how the script uses local AWS configuration, and any new dependencies or setup required.
### Acceptance Criteria (AC):
- `cc_preflight.py` can be run with minimal or no command-line arguments for common parameters like deploying principal ARN and region.
- The script interactively prompts for missing required parameters (e.g., `OrganizationalUnitId`, `ExternalID` if not default).
- Prompts for ARN and region default to values from the configured AWS environment.
- The script can list and allow selection of OUs if applicable.
- Script documentation (inline and [`README.md`](README.md)) is updated and accurate.
## Planning
- **Dependencies**: None
- **Effort**: Medium
- **Start Date**: 2025-05-16 23:23
- **End Date**: 2025-05-16 23:34
## Documentation
### Outcome/Summary:
Enhanced the cc_preflight.py script with the following features:

1. **Interactive Mode**:
   - Auto-detection of AWS profiles, regions, and identity
   - Interactive prompting for missing parameters
   - OU discovery and selection for OrganizationalUnitId parameter
   - Masking of sensitive values like ExternalID

2. **Improved IAM Simulation**:
   - Batching of actions to handle API limits
   - Special handling for wildcard actions
   - Grouping of simulation results for better readability
   - Generation of IAM policy for missing permissions

3. **Error Handling**:
   - Graceful handling of KeyboardInterrupt
   - Better error messages for AWS API errors
   - Fallbacks for when AWS resources can't be accessed

4. **Documentation**:
   - Updated README.md with new features and examples
   - Created task for addressing permission issues

Created a follow-up task (Task 6.1.3) to address the permission issues identified when testing the script against the Cortex XDR CloudFormation template.

### Issues/Blockers:
None

### Files:
- [`cc_preflight.py`](cc_preflight.py)
- [`README.md`](README.md)
- [`tasks/Phase6/task_6.1.3.md`](tasks/Phase6/task_6.1.3.md)
- [`tasks/Phase6/cortex_xdr_missing_permissions.json`](tasks/Phase6/cortex_xdr_missing_permissions.json)
- [`tasks/Phase6/outpost_role_creation_guide.md`](tasks/Phase6/outpost_role_creation_guide.md)