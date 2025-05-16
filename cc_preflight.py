#!/usr/bin/env python3
import argparse
import json
import sys
import yaml
import boto3
from botocore.exceptions import ClientError, NoCredentialsError, PartialCredentialsError
from resource_map import RESOURCE_ACTION_MAP
from value_resolver import resolve_value

def get_aws_account_id(sts_client):
    """Helper to get current AWS Account ID"""
    try:
        return sts_client.get_caller_identity()["Account"]
    except (ClientError, NoCredentialsError, PartialCredentialsError) as e:
        print(f"Error: Could not determine AWS Account ID. {e}", file=sys.stderr)
        sys.exit(1)

def evaluate_condition(condition_name, context):
    """
    Evaluates a CloudFormation condition based on input values or the template's Conditions block.
    
    Args:
        condition_name: The name of the condition to evaluate
        context: Dictionary containing template data, resolved parameters, and condition values
        
    Returns:
        Boolean result of the condition evaluation
    """
    # Check if we've already evaluated this condition (memoization)
    if "evaluated_conditions" not in context:
        context["evaluated_conditions"] = {}
    
    if condition_name in context["evaluated_conditions"]:
        return context["evaluated_conditions"][condition_name]
    
    # First check if the condition is directly provided in input values
    if "condition_values" in context and condition_name in context["condition_values"]:
        result = context["condition_values"][condition_name]
        context["evaluated_conditions"][condition_name] = result
        return result
    
    # If not in input values, check if it's defined in the template
    if "Conditions" in context["template"] and condition_name in context["template"]["Conditions"]:
        condition_def = context["template"]["Conditions"][condition_name]
        
        # Handle different intrinsic functions in conditions
        if isinstance(condition_def, dict):
            if "Fn::Equals" in condition_def:
                # Evaluate Fn::Equals
                equals_args = condition_def["Fn::Equals"]
                if len(equals_args) == 2:
                    left_value = resolve_value(equals_args[0], context["parameters"],
                                              context["account_id"], context["region"],
                                              context["template"].get("Resources", {}))
                    right_value = resolve_value(equals_args[1], context["parameters"],
                                               context["account_id"], context["region"],
                                               context["template"].get("Resources", {}))
                    result = (left_value == right_value)
                    context["evaluated_conditions"][condition_name] = result
                    return result
            
            # Handle other condition functions (not fully implemented yet)
            elif "Fn::And" in condition_def:
                print(f"Warning: Fn::And condition not fully supported yet. Defaulting to False for {condition_name}", file=sys.stderr)
                context["evaluated_conditions"][condition_name] = False
                return False
            elif "Fn::Or" in condition_def:
                print(f"Warning: Fn::Or condition not fully supported yet. Defaulting to False for {condition_name}", file=sys.stderr)
                context["evaluated_conditions"][condition_name] = False
                return False
            elif "Fn::Not" in condition_def:
                print(f"Warning: Fn::Not condition not fully supported yet. Defaulting to False for {condition_name}", file=sys.stderr)
                context["evaluated_conditions"][condition_name] = False
                return False
            elif "Fn::If" in condition_def:
                print(f"Warning: Fn::If condition not fully supported yet. Defaulting to False for {condition_name}", file=sys.stderr)
                context["evaluated_conditions"][condition_name] = False
                return False
            elif "Condition" in condition_def:
                # Reference to another condition
                referenced_condition = condition_def["Condition"]
                result = evaluate_condition(referenced_condition, context)
                context["evaluated_conditions"][condition_name] = result
                return result
    
    # If we get here, the condition wasn't found
    print(f"Error: Condition '{condition_name}' not found in input values or template.", file=sys.stderr)
    context["evaluated_conditions"][condition_name] = False
    return False

def parse_template_and_collect_actions(template_path, cfn_parameters, account_id, region, condition_values=None):
    """
    Parses the CloudFormation template and attempts to collect IAM actions
    and resource ARNs required for deployment.
    """
    print(f"\nParsing template: {template_path}...")
    actions_to_simulate = set()
    resource_arns_for_simulation = set()
    prerequisite_checks = []

    try:
        with open(template_path, 'r') as f:
            template = yaml.safe_load(f)
    except Exception as e:
        print(f"Error: Could not read or parse template file '{template_path}'. {e}", file=sys.stderr)
        sys.exit(1)

    template_parameters = template.get("Parameters", {})
    resources = template.get("Resources", {})
    
    # Create context for condition evaluation
    context = {
        "template": template,
        "parameters": {},  # Will be populated with resolved parameters
        "account_id": account_id,
        "region": region,
        "condition_values": condition_values or {}
    }
    
    # Substitute provided parameters with their defaults if not provided
    resolved_cfn_parameters = {}
    for param_key, param_def in template_parameters.items():
        if param_key in cfn_parameters:
            resolved_cfn_parameters[param_key] = cfn_parameters[param_key]
        elif "Default" in param_def:
            resolved_cfn_parameters[param_key] = param_def["Default"]
    
    # Update context with resolved parameters
    context["parameters"] = resolved_cfn_parameters

    # Check for required prerequisite parameters (example)
    if "OutpostRoleArn" in resolved_cfn_parameters:
        prerequisite_checks.append({
            "type": "iam_role_exists",
            "arn": resolved_cfn_parameters["OutpostRoleArn"],
            "description": "OutpostRoleArn parameter"
        })

    print(f"Resolved CloudFormation Parameters for pre-flight checks: {resolved_cfn_parameters}")

    for logical_id, resource_def in resources.items():
        resource_type = resource_def.get("Type")
        properties = resource_def.get("Properties", {})
        
        # Check if resource has a Condition and evaluate it
        if "Condition" in resource_def:
            condition_name = resource_def["Condition"]
            print(f"  Resource {logical_id} has condition: {condition_name}")
            
            # Evaluate the condition
            condition_result = evaluate_condition(condition_name, context)
            
            # Skip resource if condition evaluates to false
            if not condition_result:
                print(f"  Skipping resource {logical_id} due to condition {condition_name} evaluating to false")
                continue

        print(f"  Processing resource: {logical_id} (Type: {resource_type})")

        if resource_type in RESOURCE_ACTION_MAP:
            map_entry = RESOURCE_ACTION_MAP[resource_type]

            if map_entry.get("type") == "CustomResource":
                print(f"    Info: Custom Resource. Primary permissions are tied to its handler (Lambda).")
                actions_to_simulate.add("cloudformation:CreateStack")
                continue

            # 1. Add generic actions for the resource type
            actions_to_simulate.update(map_entry.get("generic_actions", []))

            # 2. Construct resource ARN pattern for simulation
            arn_pattern_str = map_entry.get("arn_pattern", "arn:aws:*:{region}:{accountId}:{resourceLogicalIdPlaceholder}/*")
            
            # Try to make ARN more specific using known properties or parameters
            resource_name_from_props = "*"
            if resource_type == "AWS::IAM::Role":
                role_name_val = properties.get("RoleName")
                if role_name_val:
                    resource_name_from_props = resolve_value(role_name_val, resolved_cfn_parameters, account_id, region, resources)
                else:
                    resource_name_from_props = f"{logical_id}-*"
            elif resource_type == "AWS::S3::Bucket":
                bucket_name_val = properties.get("BucketName")
                if bucket_name_val:
                     resource_name_from_props = resolve_value(bucket_name_val, resolved_cfn_parameters, account_id, region, resources)
                else:
                    arn_pattern_str = "arn:aws:s3:::{bucketNamePlaceholder}-*"
                    resource_name_from_props = ""
            elif resource_type in ["AWS::SQS::Queue", "AWS::SNS::Topic", "AWS::CloudTrail::Trail", "AWS::Lambda::Function"]:
                name_prop_key = None
                if resource_type == "AWS::SQS::Queue": name_prop_key = "QueueName"
                elif resource_type == "AWS::SNS::Topic": name_prop_key = "TopicName"
                elif resource_type == "AWS::CloudTrail::Trail": name_prop_key = "TrailName"
                elif resource_type == "AWS::Lambda::Function": name_prop_key = "FunctionName"

                if name_prop_key and properties.get(name_prop_key):
                    resource_name_from_props = resolve_value(properties.get(name_prop_key), resolved_cfn_parameters, account_id, region, resources)
                else:
                    resource_name_from_props = f"{logical_id}-*"
            
            # Resolve Account ID and Region
            resolved_account_id = resolve_value({"Ref": "AWS::AccountId"}, resolved_cfn_parameters, account_id, region, resources)
            resolved_region = resolve_value({"Ref": "AWS::Region"}, resolved_cfn_parameters, account_id, region, resources)

            # Substitute placeholders in ARN pattern
            current_arn = arn_pattern_str.replace("{accountId}", str(resolved_account_id) if resolved_account_id is not None else "*") \
                                      .replace("{region}", str(resolved_region) if resolved_region is not None else "*") \
                                      .replace("{roleName}", str(resource_name_from_props)) \
                                      .replace("{policyName}", str(resource_name_from_props)) \
                                      .replace("{functionName}", str(resource_name_from_props)) \
                                      .replace("{bucketName}", str(resource_name_from_props)) \
                                      .replace("{queueName}", str(resource_name_from_props)) \
                                      .replace("{topicName}", str(resource_name_from_props)) \
                                      .replace("{trailName}", str(resource_name_from_props)) \
                                      .replace("{aliasName}", str(resource_name_from_props)) \
                                      .replace("{stackSetName}", str(resource_name_from_props)) \
                                      .replace("{resourceLogicalIdPlaceholder}", logical_id)
            
            if resource_type == "AWS::S3::Bucket" and "{bucketNamePlaceholder}" in current_arn:
                 current_arn = current_arn.replace("{bucketNamePlaceholder}", f"cfn-{logical_id.lower()}")

            resource_arns_for_simulation.add(current_arn)

            # Check properties for specific actions
            property_actions_map = map_entry.get("property_actions", {})
            for prop_key, prop_actions in property_actions_map.items():
                if prop_key in properties:
                    actions_to_simulate.update(prop_actions)
                    if prop_key == "Role" and "iam:PassRole" in prop_actions:
                        role_arn_to_pass = resolve_value(properties[prop_key], resolved_cfn_parameters, account_id, region, resources)
                        if isinstance(role_arn_to_pass, str) and role_arn_to_pass.startswith("arn:"):
                            resource_arns_for_simulation.add(role_arn_to_pass)
                        else:
                            pass_role_placeholder_arn = f"arn:aws:iam::{account_id}:role/{role_arn_to_pass}-*"
                            resource_arns_for_simulation.add(pass_role_placeholder_arn)
                            print(f"    Info: Added potential PassRole ARN for simulation: {pass_role_placeholder_arn}")
        
        # Handle Tags - common across many resources
        if "Tags" in properties:
            service_prefix = resource_type.split("::")[1].lower()
            if f"{service_prefix}:TagResource" not in actions_to_simulate and \
               f"{service_prefix}:CreateTags" not in actions_to_simulate and \
               not any(action.endswith("Tagging") or action.startswith(f"{service_prefix}:Tag") \
                    for action in map_entry.get("generic_actions",[])):
                actions_to_simulate.add(f"{service_prefix}:TagResource")
                print(f"    Info: Added generic '{service_prefix}:TagResource' for Tags.")
        else:
            print(f"    Warning: No specific IAM action mapping found for resource type: {resource_type}.", file=sys.stderr)
            actions_to_simulate.add("cloudformation:CreateStack")

    return sorted(list(actions_to_simulate)), sorted(list(resource_arns_for_simulation)), prerequisite_checks


def check_prerequisites(checks, iam_client, region):
    """Checks for existence and basic configuration of prerequisite resources."""
    print("\n--- Checking Prerequisites ---")
    all_prereqs_ok = True
    for check in checks:
        print(f"  Checking: {check['description']} (ARN: {check['arn']})")
        if check["type"] == "iam_role_exists":
            try:
                iam_client.get_role(RoleName=check["arn"].split('/')[-1])
                print(f"    [PASS] Prerequisite IAM Role '{check['arn']}' exists.")
            except ClientError as e:
                if e.response['Error']['Code'] == 'NoSuchEntity':
                    print(f"    [FAIL] Prerequisite IAM Role '{check['arn']}' does not exist.")
                    all_prereqs_ok = False
                else:
                    print(f"    [ERROR] Error checking prerequisite IAM Role: {e}")
                    all_prereqs_ok = False
            except Exception as e:
                print(f"    [ERROR] Unexpected error checking prerequisite: {e}")
                all_prereqs_ok = False

    if not checks:
        print("  No specific prerequisite resource checks defined.")
    elif all_prereqs_ok:
        print("  All checked prerequisites appear to be in place.")
    else:
        print("  Some prerequisite checks failed.")
    return all_prereqs_ok


def simulate_iam_permissions(iam_client, principal_arn, actions, resource_arns, context_entries=None):
    """Simulates IAM permissions for the given principal, actions, and resources."""
    print("\n--- Simulating IAM Permissions ---")
    print(f"  Principal ARN for Simulation: {principal_arn}")
    print(f"  Actions to Simulate ({len(actions)}): {actions}")
    print(f"  Resource ARNs for Simulation ({len(resource_arns)}): {resource_arns if resource_arns else ['*']}")

    if not actions:
        print("  No actions to simulate. Skipping IAM simulation.")
        return True, []
    
    try:
        simulation_input = {
            'PolicySourceArn': principal_arn,
            'ActionNames': actions,
            'ResourceArns': resource_arns if resource_arns else ['*']
        }
        if context_entries:
            simulation_input['ContextEntries'] = context_entries
        
        response = iam_client.simulate_principal_policy(**simulation_input)
        
        all_allowed = True
        failed_simulations = []

        print("\n  Simulation Results:")
        for eval_result in response.get('EvaluationResults', []):
            eval_action_name = eval_result['EvalActionName']
            eval_decision = eval_result['EvalDecision']
            eval_resource_name = eval_result.get('EvalResourceName', '*')

            decision_marker = "[PASS]" if eval_decision == "allowed" else "[FAIL]"
            print(f"    {decision_marker} Action: {eval_action_name}, Resource: {eval_resource_name}")

            if eval_decision != "allowed":
                all_allowed = False
                failed_simulations.append(eval_result)
                if eval_result.get('OrganizationsDecisionDetail', {}).get('AllowedByOrganizations') == False:
                    print(f"      Denied by: Organizations SCP")
                if eval_result.get('PermissionsBoundaryDecisionDetail', {}).get('AllowedByPermissionsBoundary') == False:
                     print(f"      Denied by: Permissions Boundary")

        if all_allowed:
            print("\n  [SUCCESS] All simulated actions are allowed for the principal.")
        else:
            print("\n  [FAILURE] Some simulated actions were DENIED. Review details above.")
        
        return all_allowed, failed_simulations

    except ClientError as e:
        print(f"  [ERROR] IAM simulation failed: {e}", file=sys.stderr)
        return False, [{"error": str(e)}]
    except Exception as e:
        print(f"  [ERROR] An unexpected error occurred: {e}", file=sys.stderr)
        return False, [{"error": str(e)}]


def main():
    parser = argparse.ArgumentParser(description="Perform pre-flight checks for CloudFormation template.")
    parser.add_argument("--template-file", required=True, help="Path to the CloudFormation template.")
    parser.add_argument("--deploying-principal-arn", required=True, help="ARN of the deploying principal.")
    parser.add_argument("--region", required=True, help="AWS Region for deployment.")
    parser.add_argument("--parameters", nargs='*', help="CloudFormation parameters as Key=Value pairs.")
    parser.add_argument("--profile", help="AWS CLI profile to use.")
    parser.add_argument("--condition-values", help="JSON string of condition name to boolean value mappings.")

    args = parser.parse_args()

    try:
        session_params = {}
        if args.profile:
            session_params["profile_name"] = args.profile
        if args.region:
            session_params["region_name"] = args.region

        session = boto3.Session(**session_params)
        iam_client = session.client("iam")
        sts_client = session.client("sts")
        print(f"Using AWS region: {session.region_name or 'Default from config'}")
    except (PartialCredentialsError, NoCredentialsError) as e:
        print(f"Error: AWS credentials issue. {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error: Could not initialize AWS session. {e}", file=sys.stderr)
        sys.exit(1)

    account_id = get_aws_account_id(sts_client)

    # Parse CLI parameters
    cfn_cli_parameters = {}
    if args.parameters:
        for p_item in args.parameters:
            if "=" not in p_item:
                print(f"Error: Parameter '{p_item}' is not in Key=Value format.", file=sys.stderr)
                sys.exit(1)
            key, value = p_item.split("=", 1)
            cfn_cli_parameters[key] = value
    
    # Parse condition values if provided
    condition_values = None
    if args.condition_values:
        try:
            condition_values = json.loads(args.condition_values)
            print(f"Using provided condition values: {condition_values}")
        except json.JSONDecodeError as e:
            print(f"Error: Could not parse condition values JSON. {e}", file=sys.stderr)
            sys.exit(1)
    
    # Step 1: Parse Template & Collect Actions
    actions, resource_arns, prerequisite_checks = parse_template_and_collect_actions(
        args.template_file, cfn_cli_parameters, account_id, args.region, condition_values
    )

    # Step 2: Check Prerequisites
    prereqs_ok = check_prerequisites(prerequisite_checks, iam_client, args.region)

    # Step 3: Simulate IAM Permissions
    context_entries = []
    if "ExternalID" in cfn_cli_parameters:
        context_entries.append({
            "ContextKeyName": "sts:ExternalId",
            "ContextKeyValues": [cfn_cli_parameters["ExternalID"]],
            "ContextKeyType": "string"
        })

    permissions_ok, failed_sims = simulate_iam_permissions(
        iam_client, args.deploying_principal_arn, actions, resource_arns, context_entries
    )

    # Final Summary
    print("\n--- Pre-flight Check Summary ---")
    if prereqs_ok:
        print("[PASS] Prerequisite checks passed or no prerequisites to check.")
    else:
        print("[FAIL] Some prerequisite checks failed.")

    if permissions_ok:
        print("[PASS] IAM permission simulation indicates all permissions are present.")
    else:
        print("[FAIL] IAM permission simulation indicates missing permissions.")
        print("        Review the simulation details above for denied actions.")

    if prereqs_ok and permissions_ok:
        print("\nPre-flight checks completed successfully.")
        sys.exit(0)
    else:
        print("\nPre-flight checks identified issues. Review failures before deploying.")
        sys.exit(1)


if __name__ == "__main__":
    main()