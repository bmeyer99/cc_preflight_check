# Task Status (DO NOT DELETE)
- **ID**: 6.1.1
- **Title**: Pre-flight Check AWS Permissions for Cortex XDR CFT
- **AssignedTo**: Archer
- **From**: User Request
- **Priority**: High
- **Status**: Blocked
## Details
### Requirements:
- Use the `cc_preflight.py` script to analyze the `connectors_aws_cf-d33f925f6195475daf212fdc8b1919e2-1747407759.yml` CFT.
- Check if the user's AWS account has the necessary IAM permissions to deploy the CFT.
- Only execute the `cc_preflight.py` script for testing against the AWS account. No other AWS commands should be run.
- If errors occur during the script execution (e.g., permission denials), create a new task to address these errors, ensuring the new task reiterates that fixes should only be tested via the script.
### Acceptance Criteria (AC):
- The `cc_preflight.py` script is executed with the correct parameters (interactively determined post Task 6.1.2).
- The output of the script, indicating permission status, is available.
- A follow-up task is created if permission issues are identified.
## Planning
- **Dependencies**: Task 6.1.2 (Enhance `cc_preflight.py` for Interactive Input & AWS Config Detection)
- **Effort**: Short
- **Start Date**: 2025-05-16 23:19
- **End Date**:
## Documentation
### Outcome/Summary:
### Issues/Blockers:
- Blocked by Task 6.1.2. Script needs enhancements before it can be run as requested.
### Files:
- [`connectors_aws_cf-d33f925f6195475daf212fdc8b1919e2-1747407759.yml`](connectors_aws_cf-d33f925f6195475daf212fdc8b1919e2-1747407759.yml)
- [`cc_preflight.py`](cc_preflight.py)