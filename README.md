# AWS CloudFormation Pre-flight Check Tool (cc_preflight)

**Version:** 3.0
**Last Updated:** May 16, 2025

## 1. Overview

The CloudFormation Pre-flight Check Tool (`cc_preflight.py`) is a powerful utility designed to analyze AWS CloudFormation templates before deployment. It proactively identifies potential IAM permission insufficiencies and missing prerequisite resources, significantly reducing the likelihood of CloudFormation stack deployment failures.

The tool dynamically analyzes CloudFormation templates to understand what AWS resources they intend to create or modify, then simulates whether the specified IAM principal (the one designated to deploy the stack) possesses the necessary permissions for these operations. It also verifies the existence of prerequisite resources referenced in the template.

### Core Functionality

- **IAM Permission Simulation**: Verifies that the deploying principal has all required permissions to create and configure resources defined in the template.
- **Prerequisite Resource Validation**: Checks for the existence of external AWS resources that the template depends on.
- **Intrinsic Function Resolution**: Resolves CloudFormation intrinsic functions to accurately predict resource names and ARNs.
- **Condition Evaluation**: Evaluates CloudFormation conditions to determine which resources will actually be created.
- **Resource-to-Action Mapping**: Maps CloudFormation resources to the specific IAM actions required for their creation and configuration.

## 2. Features

### Intrinsic Function Resolution

The tool supports resolution of the following CloudFormation intrinsic functions:

- **`Ref`**: Resolves references to parameters, pseudo-parameters, and other resources.
- **`Fn::Sub`**: Handles string substitutions, including references to parameters and pseudo-parameters.
- **`Fn::GetAtt`**: Resolves attributes of resources defined in the template.
- **`Fn::Join`**: Joins a list of values with a specified delimiter.

### Condition Handling

The tool evaluates CloudFormation conditions to determine which resources will be created:

- **Direct Condition Values**: Conditions can be provided directly via the `--condition-values` parameter.
- **`Fn::Equals`**: Fully supported for comparing values.
- **Condition References**: Supports references to other conditions.
- **Other Condition Functions**: Basic support for `Fn::And`, `Fn::Or`, `Fn::Not`, and `Fn::If` (with limitations).

### Resource-to-Action Mapping

The `RESOURCE_ACTION_MAP` is a comprehensive dictionary that maps CloudFormation resource types to:

- **Generic Actions**: Common IAM actions required for creating, updating, and deleting resources.
- **ARN Patterns**: Templates for constructing resource ARN patterns for IAM simulation.
- **Property-Specific Actions**: Additional IAM actions required based on specific resource properties.
- **Operation-Specific Actions**: Actions required for specific operations (Create, Update, Delete, Tag).

The map currently supports a wide range of AWS resource types, including:
- IAM Roles and Policies
- Lambda Functions
- S3 Buckets
- SQS Queues
- SNS Topics
- KMS Keys
- CloudTrail Trails
- CloudFormation StackSets
- Custom Resources

### ARN Construction and Pseudo-Parameter Resolution

The tool constructs ARN patterns for IAM simulation by:

- Resolving resource names from properties or generating default names.
- Substituting account ID, region, and resource names into ARN patterns.
- Handling special cases for different resource types.

Pseudo-parameters like `AWS::AccountId`, `AWS::Region`, and `AWS::StackName` are automatically resolved.

### Prerequisite Checking

The tool verifies the existence of prerequisite resources referenced in the template, such as:

- IAM roles specified in parameters (e.g., `OutpostRoleArn`).
- Other external resources that the template depends on.

### IAM Permission Simulation

The core of the tool is the IAM permission simulation, which:

- Uses the AWS IAM `simulate_principal_policy` API.
- Simulates whether the deploying principal can perform all required actions on the predicted resource ARNs.
- Supports context entries for condition keys (e.g., `sts:ExternalId`).
- Provides detailed results showing which actions are allowed and which are denied.

## 3. Usage

### Prerequisites

- **Python 3.8+**
- **Required Python Packages**:
  ```bash
  pip install boto3 pyyaml
  ```
- **AWS Credentials**: The IAM identity running the script needs permissions for:
  - `iam:SimulatePrincipalPolicy`
  - `sts:GetCallerIdentity`
  - Permissions to describe any prerequisite resources
  - `organizations:ListRoots` and `organizations:ListOrganizationalUnitsForParent` (if using OU discovery)

### Interactive Mode (New)

The tool now supports an interactive mode that automatically detects AWS configurations and prompts for missing parameters:

```bash
python cc_preflight.py --template-file <path_to_cloudformation_template>
```

In interactive mode, the tool will:

1. **Auto-detect AWS profile** - Lists available profiles and lets you select one
2. **Auto-detect AWS region** - Uses the default region from your AWS config or prompts for selection
3. **Auto-detect deploying principal** - Uses your current AWS identity
4. **Prompt for CloudFormation parameters** - Prompts for any required parameters with defaults from the template
5. **Discover Organizational Units** - For templates requiring an `OrganizationalUnitId`, lists available OUs for selection
6. **Generate IAM policy** - Offers to generate an IAM policy document for any missing permissions

### Command-Line Arguments

```bash
python cc_preflight.py \
    --template-file <path_to_cloudformation_template> \
    [--deploying-principal-arn <arn_of_deploying_principal>] \
    [--region <aws_region>] \
    [--parameters <key1=value1> <key2=value2> ...] \
    [--profile <aws_cli_profile>] \
    [--condition-values <json_string_of_condition_values>] \
    [--non-interactive]
```

#### Required Arguments

- **`--template-file`**: Path to the CloudFormation template file (YAML or JSON).

#### Optional Arguments

- **`--deploying-principal-arn`**: ARN of the IAM principal that will deploy the CloudFormation stack. If not provided, will use current identity or prompt.
- **`--region`**: AWS region where the stack will be deployed. If not provided, will use default region or prompt.
- **`--parameters`**: CloudFormation parameters as key-value pairs (e.g., `OutpostRoleArn=arn:aws:iam::123456789012:role/MyRole`).
- **`--profile`**: AWS CLI profile to use for API calls.
- **`--condition-values`**: JSON string of condition name to boolean value mappings (e.g., `{"IsProduction": true, "EnableFeatureX": false}`).
- **`--non-interactive`**: Run in non-interactive mode (no prompts). In this mode, all required parameters must be provided via command-line arguments.

### Example Commands

#### Interactive Mode (Recommended)

```bash
# Minimal command - will prompt for all required information
python cc_preflight.py --template-file ./my-cloudformation-template.yml
```

#### Basic Usage with Command-Line Arguments

```bash
python cc_preflight.py \
    --template-file ./my-cloudformation-template.yml \
    --deploying-principal-arn arn:aws:iam::123456789012:role/DeploymentRole \
    --region us-east-1
```

#### With Parameters and Profile

```bash
python cc_preflight.py \
    --template-file ./my-cloudformation-template.yml \
    --deploying-principal-arn arn:aws:iam::123456789012:role/DeploymentRole \
    --region us-east-1 \
    --parameters "BucketName=my-unique-bucket" "RoleName=MyServiceRole" \
    --profile my-aws-profile
```

#### With Condition Values

```bash
python cc_preflight.py \
    --template-file ./my-cloudformation-template.yml \
    --deploying-principal-arn arn:aws:iam::123456789012:role/DeploymentRole \
    --region us-east-1 \
    --condition-values '{"IsProduction": true, "EnableEncryption": true}'
```

#### Non-Interactive Mode

```bash
python cc_preflight.py \
    --template-file ./my-cloudformation-template.yml \
    --deploying-principal-arn arn:aws:iam::123456789012:role/DeploymentRole \
    --region us-east-1 \
    --parameters "OrganizationalUnitId=r-abc123" "ExternalID=abcdef-123456" \
    --non-interactive
```

### Understanding the Output

The tool provides detailed output at each stage of the analysis:

1. **AWS Configuration**: Shows detected or selected AWS profile, region, and identity.
2. **CloudFormation Parameters**: Lists the parameters being used for the template.
3. **Template Parsing**: Shows resolved parameters and processed resources.
4. **Prerequisite Checks**: Reports whether all prerequisite resources exist.
5. **IAM Simulation**: Lists all actions to be simulated and their results (PASS/FAIL).
6. **Policy Generation**: If permissions are missing, offers to generate an IAM policy document.
7. **Summary**: Provides an overall assessment of whether the deployment is likely to succeed.

Example output:
```
Parsing template: ./my-cloudformation-template.yml...
Resolved CloudFormation Parameters for pre-flight checks: {'BucketName': 'my-unique-bucket', 'RoleName': 'MyServiceRole'}
  Processing resource: MyS3Bucket (Type: AWS::S3::Bucket)
  Processing resource: MyIAMRole (Type: AWS::IAM::Role)
  ...

--- Checking Prerequisites ---
  No specific prerequisite resource checks defined.
  All checked prerequisites appear to be in place.

--- Simulating IAM Permissions ---
  Principal ARN for Simulation: arn:aws:iam::123456789012:role/DeploymentRole
  Actions to Simulate (12): ['iam:CreateRole', 'iam:DeleteRole', 'iam:PutRolePolicy', 'iam:TagRole', ...]
  Resource ARNs for Simulation (2): ['arn:aws:iam::123456789012:role/MyServiceRole', 'arn:aws:s3:::my-unique-bucket']

  Simulation Results:
    [PASS] Action: iam:CreateRole, Resource: arn:aws:iam::123456789012:role/MyServiceRole
    [PASS] Action: iam:TagRole, Resource: arn:aws:iam::123456789012:role/MyServiceRole
    ...
    [FAIL] Action: s3:CreateBucket, Resource: arn:aws:s3:::my-unique-bucket
    ...

--- Pre-flight Check Summary ---
[PASS] Prerequisite checks passed or no prerequisites to check.
[FAIL] IAM permission simulation indicates missing permissions.
       Review the simulation details above for denied actions.

Pre-flight checks identified issues. Review failures before deploying.
```

## 4. New Features

### AWS Configuration Auto-Detection

The tool now automatically detects and uses:

- **AWS CLI Profiles**: Lists available profiles and allows selection
- **Default Region**: Uses the region from your AWS config
- **Current Identity**: Uses your current AWS identity for permission simulation

### Interactive Parameter Prompting

For any required CloudFormation parameters not provided via command-line:

- **Default Values**: Uses default values from the template when available
- **Parameter Descriptions**: Shows parameter descriptions from the template
- **Sensitive Values**: Masks sensitive values like ExternalID in the output

### AWS Organizations Integration

For templates that require an `OrganizationalUnitId` parameter:

- **OU Discovery**: Lists all OUs in your AWS Organization
- **OU Selection**: Allows selection from the list or manual entry
- **Path Display**: Shows the full path of each OU for easier identification

### IAM Policy Generation

When permission simulation fails:

- **Policy Document**: Generates an IAM policy document for the missing permissions
- **Resource Grouping**: Groups actions by resource for better organization
- **JSON Format**: Outputs the policy in JSON format ready to use in IAM

## 5. Known Limitations

- **Intrinsic Function Resolution**:
  - Limited support for complex `Fn::Sub` list forms.
  - `Fn::GetAtt` resolution for non-existent resources uses placeholders.
  - Complex nested intrinsic functions may not be fully resolved.

- **Condition Evaluation**:
  - Limited support for complex condition functions like `Fn::And`, `Fn::Or`, and `Fn::Not`.
  - Defaults to `false` for unsupported condition functions.

- **IAM Simulation Accuracy**:
  - Uses wildcard ARNs for resources that don't yet exist, which may lead to false positives if policies are narrowly scoped.
  - May not perfectly replicate every real-world authorization scenario, especially those involving complex IAM condition keys.

- **CloudFormation StackSet Limitations**:
  - For `AWS::CloudFormation::StackSet` resources, the tool primarily checks permissions to create and manage the StackSet itself, not the permissions needed for stack instances in target accounts.

- **Custom Resource Limitations**:
  - For custom resources, the tool checks permissions to create the backing Lambda function and its IAM execution role, but cannot validate the internal logic or actions performed by the Lambda function code itself.

- **Dynamic Naming**:
  - CloudFormation often appends unique suffixes to resource names. The tool uses logical IDs or patterns as placeholders, which may not match the exact physical IDs.

- **AWS Organizations Access**:
  - OU discovery requires `organizations:ListRoots` and `organizations:ListOrganizationalUnitsForParent` permissions.
  - If these permissions are not available, the tool will fall back to manual input for the `OrganizationalUnitId` parameter.

## 5. Extending the Tool

### Adding Support for New Resource Types

To add support for a new AWS resource type, update the `RESOURCE_ACTION_MAP` in `resource_map.py`:

```python
RESOURCE_ACTION_MAP["AWS::NewService::NewResource"] = {
    "generic_actions": [
        "newservice:CreateResource",
        "newservice:DeleteResource",
        "newservice:TagResource"
    ],
    "arn_pattern": "arn:aws:newservice:{region}:{accountId}:resource/{resourceName}",
    "property_actions": {
        "SomeProperty": ["newservice:ConfigureProperty"]
    },
    "operation_actions": {
        "Create": ["newservice:CreateResource", "newservice:TagResource"],
        "Update": ["newservice:UpdateResource", "newservice:TagResource"],
        "Delete": ["newservice:DeleteResource"],
        "Tag": ["newservice:TagResource"]
    }
}
```

### Improving Intrinsic Function Resolution

To enhance intrinsic function resolution, modify the functions in `value_resolver.py`:

- **`resolve_ref`**: Improve handling of references to logical resources.
- **`resolve_sub`**: Enhance support for the list form of `Fn::Sub`.
- **`resolve_get_att`**: Add support for more resource types and attributes.
- Add new functions for other intrinsic functions like `Fn::ImportValue`, `Fn::Select`, etc.

### Adding New Prerequisite Checks

To add new types of prerequisite checks, update the `check_prerequisites` function in `cc_preflight.py`:

```python
if check["type"] == "s3_bucket_exists":
    try:
        s3_client = boto3.client('s3')
        s3_client.head_bucket(Bucket=check["bucket_name"])
        print(f"    [PASS] Prerequisite S3 Bucket '{check['bucket_name']}' exists.")
    except ClientError as e:
        print(f"    [FAIL] Prerequisite S3 Bucket '{check['bucket_name']}' does not exist.")
        all_prereqs_ok = False
```

Then update the `parse_template_and_collect_actions` function to identify and add these new prerequisite checks.

## 6. Conclusion

The CloudFormation Pre-flight Check Tool is a valuable utility for AWS infrastructure deployments, helping to identify and resolve permission issues and missing prerequisites before they cause deployment failures. By providing detailed simulation results and clear error messages, it significantly improves the CloudFormation deployment experience.

While the tool has some limitations, particularly around complex intrinsic function resolution and certain condition evaluations, it provides a solid foundation that can be extended and enhanced to meet specific needs.

## 7. License

This tool is provided as-is without any warranties. Use at your own risk.
