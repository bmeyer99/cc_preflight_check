# Task Status (DO NOT DELETE)
- **ID**: 7.1.2
- **Title**: Verify IAM Preflight Check Script Output and Admin Permissions
- **AssignedTo**: Archer (architect)
- **From**: User Request
- **Priority**: High
- **Status**: Pending Review
## Details
### Requirements:
- Analyze the output of the `cc_preflight.py` script when checking `connectors_aws_cf-d33f925f6195475daf212fdc8b1919e2-1747407759.yml`.
- Determine why the script reports missing permissions for the admin user `arn:aws:iam::805659904417:user/3DPFPP`.
- Determine why the script reports the prerequisite IAM role `arn:aws:iam::650251731026:role/gcp_saas_role` as non-existent.
- Provide a plan to verify the actual required permissions against the admin user's capabilities and the prerequisite role's status.

### Acceptance Criteria (AC):
- A clear explanation of the `cc_preflight.py` script's behavior regarding permission checks and prerequisite validation is documented.
- A plausible explanation for the discrepancies observed in the script output (missing admin permissions, non-existent prerequisite role) is provided.
- A step-by-step plan is created for the user to independently verify the findings concerning their IAM permissions and the prerequisite role.
## Planning
- **Dependencies**: None
- **Effort**: Medium
- **Start Date**: 2025-05-17 00:24
- **End Date**: 2025-05-17 00:30
## Documentation
### Outcome/Summary:
Analyzed the `cc_preflight.py` script and its modules (`cli_handler.py`, `template_analyzer.py`, `resource_map.py`, `iam_prerequisites.py`, `iam_simulator.py`).

**Key Findings:**
1.  **Prerequisite `OutpostRoleArn` Failure**:
    *   The script checks for the existence of `arn:aws:iam::650251731026:role/gcp_saas_role` by calling `iam_client.get_role(RoleName="gcp_saas_role")`.
    *   This `iam_client` is configured for the deploying principal's account (805659904417).
    *   Thus, the script is effectively checking if `arn:aws:iam::805659904417:role/gcp_saas_role` exists, not the role in account `650251731026`. This is the likely reason for the "does not exist" failure if the role is not in account 805659904417.

2.  **IAM Simulation `implicitDeny` for Admin User (6 specific actions)**:
    *   The script simulates 81 actions. 6 actions (`cloudformation:CreateStack`, `cloudformation:CreateStackSet`, `kms:CreateKey`, `organizations:ListAWSServiceAccessForOrganization`, `sns:SetSubscriptionAttributes`, and one other) are consistently reported as `implicitDeny` for all 19 resource ARNs.
    *   The `iam_simulator.py` calls `iam_client.simulate_principal_policy()` for each action individually, against all resource ARNs, and includes a `ContextEntry` for `sts:ExternalId` (value: `d5e1e7e8-58c1-430d-8326-65c5a0d8171c`).
    *   **Hypothesis**: The `implicitDeny` is likely due to:
        *   The `sts:ExternalId` context key being applied to simulations of direct user actions. The IAM simulator might not find an allow policy matching this context for non-assume-role actions.
        *   Potential issues simulating global/non-resource-specific actions (like `organizations:ListAWSServiceAccessForOrganization`) against specific resource ARNs.
    *   The script output does not indicate denials from SCPs or Permission Boundaries.

**Verification Plan for User:**
1.  **Prerequisite Role Verification**:
    *   Confirm that the role `arn:aws:iam::650251731026:role/gcp_saas_role` exists in AWS account `650251731026`.
    *   Note that the script currently checks for this role in the deploying account (805659904417).

2.  **IAM Simulation Verification (using AWS CLI)**:
    *   Replace `<your_aws_profile_for_account_805659904417>` with the actual AWS CLI profile name.
    *   **Test 1 (kms:CreateKey without ExternalId)**:
        ```bash
        aws iam simulate-principal-policy --policy-source-arn "arn:aws:iam::805659904417:user/3DPFPP" --action-names "kms:CreateKey" --resource-arns "arn:aws:kms:us-east-1:805659904417:key/*" --profile <your_aws_profile_for_account_805659904417> --region us-east-1
        ```
    *   **Test 2 (kms:CreateKey with ExternalId)**:
        ```bash
        aws iam simulate-principal-policy --policy-source-arn "arn:aws:iam::805659904417:user/3DPFPP" --action-names "kms:CreateKey" --resource-arns "arn:aws:kms:us-east-1:805659904417:key/*" --context-entries '[{"ContextKeyName":"sts:ExternalId","ContextKeyValues":["d5e1e7e8-58c1-430d-8326-65c5a0d8171c"],"ContextKeyType":"string"}]' --profile <your_aws_profile_for_account_805659904417> --region us-east-1
        ```
    *   **Test 3 (organizations:ListAWSServiceAccessForOrganization without ExternalId, global resource)**:
        ```bash
        aws iam simulate-principal-policy --policy-source-arn "arn:aws:iam::805659904417:user/3DPFPP" --action-names "organizations:ListAWSServiceAccessForOrganization" --resource-arns "*" --profile <your_aws_profile_for_account_805659904417> --region us-east-1
        ```
    *   **Test 4 (organizations:ListAWSServiceAccessForOrganization with ExternalId, global resource)**:
        ```bash
        aws iam simulate-principal-policy --policy-source-arn "arn:aws:iam::805659904417:user/3DPFPP" --action-names "organizations:ListAWSServiceAccessForOrganization" --resource-arns "*" --context-entries '[{"ContextKeyName":"sts:ExternalId","ContextKeyValues":["d5e1e7e8-58c1-430d-8326-65c5a0d8171c"],"ContextKeyType":"string"}]' --profile <your_aws_profile_for_account_805659904417> --region us-east-1
        ```
    Comparing the results of these tests will help isolate the cause of the `implicitDeny` messages.

### Issues/Blockers:
- The script's prerequisite check for `OutpostRoleArn` appears to check against the deploying account rather than the target account specified in the ARN.

### Files:
- [`cc_preflight.py`](cc_preflight.py:1)
- [`cli_handler.py`](cli_handler.py:1)
- [`template_analyzer.py`](template_analyzer.py:1)
- [`resource_map.py`](resource_map.py:1)
- [`iam_prerequisites.py`](iam_prerequisites.py:1)
- [`iam_simulator.py`](iam_simulator.py:1)
- [`connectors_aws_cf-d33f925f6195475daf212fdc8b1919e2-1747407759.yml`](connectors_aws_cf-d33f925f6195475daf212fdc8b1919e2-1747407759.yml:1)
- Script output provided by user.