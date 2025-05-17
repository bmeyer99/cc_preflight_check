# Task Status (DO NOT DELETE)
- **ID**: 6.1.2.1
- **Title**: Implement Enhanced Argument Parsing and Interactive Prompts for Core Parameters in `cc_preflight.py`
- **AssignedTo**: Archer
- **From**: Task 6.1.2
- **Priority**: High
- **Status**: Assigned
## Details
### Requirements:
- Modify `argparse` in `cc_preflight.py` to make `--deploying-principal-arn` and `--region` optional command-line arguments.
- If `deploying-principal-arn` is not provided, use `boto3.client('sts').get_caller_identity()["Arn"]` to fetch it and use as default. Prompt if fetch fails.
- If `region` is not provided, use `boto3.Session().region_name` to fetch it. Prompt if not configured.
- Check the CloudFormation template for `OrganizationalUnitId` and `ExternalID` parameters.
- If these parameters exist in the CFT and are not provided as arguments:
    - Prompt for `OrganizationalUnitId`.
    - Prompt for `ExternalID`, using the CFT's default value as the prompt's default.
- If `--profile` is not provided, attempt to use the default AWS CLI profile. If multiple profiles exist or none are configured clearly, prompt the user to specify one or confirm the default.
- Prompt for `--condition-values` (as a JSON string) if this argument is relevant and not provided.
- Ensure all prompts clearly state what information is needed and provide context (e.g., "Enter the AWS Region for deployment (default: us-east-1):").
### Acceptance Criteria (AC):
- `cc_preflight.py` can be run without `--deploying-principal-arn` and `--region` if AWS environment is configured.
- Script correctly fetches and uses/prompts for default ARN and region.
- Script prompts for `OrganizationalUnitId` and `ExternalID` (with CFT default) if applicable and not provided.
- Script handles AWS CLI profile selection/confirmation.
- Interactive prompts are user-friendly and provide necessary defaults.
## Planning
- **Dependencies**: None
- **Effort**: Medium
- **Start Date**: 2025-05-16 23:23
- **End Date**:
## Documentation
### Outcome/Summary:
### Issues/Blockers:
### Files:
- [`cc_preflight.py`](cc_preflight.py)