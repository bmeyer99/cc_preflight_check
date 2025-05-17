# Task Status (DO NOT DELETE)
- **ID**: 6.1.2.2
- **Title**: Implement AWS Organizations OU Discovery and Selection in `cc_preflight.py`
- **AssignedTo**: Archer
- **From**: Task 6.1.2
- **Priority**: High
- **Status**: Assigned
## Details
### Requirements:
- In `cc_preflight.py`, after core parameters are resolved (interactively or via CLI), check if the provided CloudFormation template (e.g., [`connectors_aws_cf-d33f925f6195475daf212fdc8b1919e2-1747407759.yml`](connectors_aws_cf-d33f925f6195475daf212fdc8b1919e2-1747407759.yml)) contains an `OrganizationalUnitId` parameter (see line 4 of the example CFT).
- If the `OrganizationalUnitId` parameter is present in the CFT and its value has not yet been provided (either via CLI or the initial interactive prompt in Task 6.1.2.1):
    - Initialize a `boto3.client('organizations')`.
    - Attempt to call `organizations_client.list_roots()`.
        - If successful and roots are found, take the first root ID.
        - Implement a recursive function or iterative approach to:
            - Call `organizations_client.list_organizational_units_for_parent(ParentId=current_parent_id)`
            - Call `organizations_client.list_accounts_for_parent(ParentId=current_parent_id)` (Optional, for context, but selection is for OUs).
            - Collate all discovered Organizational Units (OUs), storing their Name and ID.
        - Present the user with a numbered list of discovered OU Names and IDs.
        - Prompt the user to select an OU by number, or to enter an OU ID manually if not listed.
        - Use the selected/entered OU ID as the value for the `OrganizationalUnitId` CFT parameter.
    - Handle potential exceptions gracefully:
        - `AWSOrganizationsNotInUseException`: Inform the user that the account is not part of an AWS Organization and this parameter might not be usable or requires manual input.
        - `AccessDeniedException`: Inform the user that permissions are insufficient to list OUs and `OrganizationalUnitId` must be provided manually.
        - Other `ClientError` exceptions: Provide a generic error message.
- If the `OrganizationalUnitId` parameter is not in the CFT, or if its value was already provided, skip this OU discovery step.
### Acceptance Criteria (AC):
- Script correctly identifies if `OrganizationalUnitId` is a required, unprovided parameter.
- Script successfully lists OUs from the AWS Organization if permissions allow.
- User is presented with a clear, selectable list of OUs.
- User's selection is correctly used for the `OrganizationalUnitId` parameter.
- Script handles cases where the account is not in an Organization or lacks permissions to list OUs.
## Planning
- **Dependencies**: Task 6.1.2.1 (for initial parameter handling)
- **Effort**: Medium
- **Start Date**: 2025-05-16 23:23
- **End Date**:
## Documentation
### Outcome/Summary:
### Issues/Blockers:
### Files:
- [`cc_preflight.py`](cc_preflight.py)
- [`connectors_aws_cf-d33f925f6195475daf212fdc8b1919e2-1747407759.yml`](connectors_aws_cf-d33f925f6195475daf212fdc8b1919e2-1747407759.yml)