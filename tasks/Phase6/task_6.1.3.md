# Task Status (DO NOT DELETE)
- **ID**: 6.1.3
- **Title**: Fix Permissions for Cortex XDR CloudFormation Template Deployment
- **AssignedTo**: Code
- **From**: Task 6.1.2
- **Priority**: High
- **Status**: Assigned

## Details
### Requirements:
- Address the permission issues identified by the cc_preflight.py script when checking the Cortex XDR CloudFormation template
- Create IAM policy document for the missing permissions
- Ensure the prerequisite OutpostRoleArn exists or provide guidance on creating it

### Acceptance Criteria (AC):
- IAM policy document created for the missing permissions
- Clear documentation on how to create the OutpostRoleArn prerequisite
- All pre-flight checks pass when running the script against the template

## Planning
- **Dependencies**: Task 6.1.2
- **Effort**: Medium
- **Start Date**: 2025-05-16 23:33
- **End Date**: TBD

## Documentation
### Outcome/Summary:
The cc_preflight.py script identified the following issues when checking the Cortex XDR CloudFormation template:

1. **Missing Prerequisite**:
   - The OutpostRoleArn parameter (arn:aws:iam::650251731026:role/gcp_saas_role) does not exist in the account.

2. **Missing Permissions**:
   The following actions are denied for all resources:
   - cloudformation:CreateStack
   - cloudformation:CreateStackSet
   - kms:CreateKey
   - organizations:ListAWSServiceAccessForOrganization
   - sns:SetSubscriptionAttributes
   - sns:SetTopicAttributes

### Important Note:
As per the instructions, we must not interact with AWS directly. All testing must be done through the cc_preflight.py script. The script is designed to check if the account has the necessary permissions to deploy the CloudFormation template, but it does not actually deploy anything.

### Files:
- connectors_aws_cf-d33f925f6195475daf212fdc8b1919e2-1747407759.yml
- cc_preflight.py
- tasks/Phase6/cortex_xdr_missing_permissions.json
- tasks/Phase6/outpost_role_creation_guide.md