# Guide to Creating the OutpostRoleArn Prerequisite

## Overview

The Cortex XDR CloudFormation template requires an existing IAM role in the Palo Alto Networks outpost account (650251731026) with the ARN `arn:aws:iam::650251731026:role/gcp_saas_role`. This role is used as a trust relationship for cross-account access.

## Steps to Create the Role

Since this role exists in the Palo Alto Networks account (650251731026) and not in your account, you cannot create it directly. Instead, you need to:

1. **Contact Palo Alto Networks Support**: Reach out to Palo Alto Networks support and inform them that you need the `gcp_saas_role` role to be created in their account for Cortex XDR integration.

2. **Provide Your Account ID**: They will need your AWS account ID to establish the proper trust relationship.

3. **Verify Role Creation**: Once they confirm the role has been created, you can verify it by running the cc_preflight.py script again to check if the prerequisite check passes.

## Alternative Approach

If you cannot get the exact role created in the Palo Alto Networks account, you may need to modify the CloudFormation template to use a different role ARN:

1. Edit the template parameter `OutpostRoleArn` to use a role ARN that does exist or that you can create.

2. Update the template to use this new role ARN in all relevant places.

3. Ensure that the new role has the necessary permissions and trust relationships required for Cortex XDR integration.

## Required Trust Relationship

The role in the Palo Alto Networks account should have a trust relationship that allows your account to assume it. The trust policy should look similar to:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "AWS": "arn:aws:iam::<YOUR_ACCOUNT_ID>:root"
      },
      "Action": "sts:AssumeRole",
      "Condition": {
        "StringEquals": {
          "sts:ExternalId": "<EXTERNAL_ID_FROM_TEMPLATE>"
        }
      }
    }
  ]
}
```

Where:
- `<YOUR_ACCOUNT_ID>` is your AWS account ID
- `<EXTERNAL_ID_FROM_TEMPLATE>` is the ExternalID parameter from the CloudFormation template (default: d5e1e7e8-58c1-430d-8326-65c5a0d8171c)

## Important Note

Remember that you should not interact directly with AWS to test this. All testing should be done through the cc_preflight.py script, which will check if the prerequisites are in place without actually deploying anything.