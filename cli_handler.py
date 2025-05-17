#!/usr/bin/env python3
"""
Command-Line Interface Handler.

This module provides functionality for handling command-line arguments,
user interaction, and parameter handling for the CloudFormation Pre-flight
Check Tool. It includes the main entry point for the tool.
"""

import sys
import os
import argparse
import json
import getpass
from typing import Dict, List, Any, Optional

import boto3
from botocore.exceptions import ClientError, NoCredentialsError, PartialCredentialsError, ProfileNotFound

from cc_preflight_exceptions import InputError, AWSError
from aws_utils import get_aws_account_id, get_aws_profiles, get_current_identity, list_organizational_units
from cfn_yaml_handler import get_template_parameters
from template_analyzer import parse_template_and_collect_actions
from iam_prerequisites import check_prerequisites
from iam_simulator import simulate_iam_permissions


def prompt_user(prompt_text: str, default_value: Optional[str] = None) -> str:
    """
    Prompt the user for input with an optional default value.
    
    Args:
        prompt_text: The text to display to the user
        default_value: Optional default value to use if the user presses Enter
        
    Returns:
        The user's input or the default value if provided and user pressed Enter
    """
    if default_value:
        full_prompt = f"{prompt_text} (default: {default_value}): "
    else:
        full_prompt = f"{prompt_text}: "
    
    user_input = input(full_prompt).strip()
    
    if not user_input and default_value:
        return default_value
    
    return user_input


def main() -> None:
    """
    Main entry point for the CloudFormation pre-flight check tool.
    
    This function:
    1. Parses command line arguments
    2. Initializes AWS clients (IAM, STS)
    3. Parses the CloudFormation template
    4. Collects required IAM actions and resource ARNs
    5. Checks for prerequisite resources
    6. Simulates IAM permissions
    7. Provides a summary of the results
    
    The tool exits with status code 0 if all checks pass, 1 otherwise.
    
    Command line arguments:
    --template-file: Path to the CloudFormation template
    --deploying-principal-arn: ARN of the principal deploying the template
    --region: AWS region for deployment
    --parameters: CloudFormation parameters as Key=Value pairs
    --profile: AWS CLI profile to use
    --condition-values: JSON string of condition name to boolean value mappings
    """
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Perform pre-flight checks for CloudFormation template.")
    parser.add_argument("--template-file", required=True, help="Path to the CloudFormation template.")
    parser.add_argument("--deploying-principal-arn", help="ARN of the principal deploying the template. If not provided, will use current identity or prompt.")
    parser.add_argument("--region", help="AWS Region for deployment. If not provided, will use default region or prompt.")
    parser.add_argument("--parameters", nargs='*', help="CloudFormation parameters as Key=Value pairs.")
    parser.add_argument("--profile", help="AWS CLI profile to use.")
    parser.add_argument("--condition-values", help="JSON string of condition name to boolean value mappings.")
    parser.add_argument("--non-interactive", action="store_true", help="Run in non-interactive mode (no prompts).")
    parser.add_argument("--no-pdf", action="store_true", help="Skip generating a PDF report of the pre-flight check results.")
    parser.add_argument("--pdf-output", help="Path to save the PDF report. If not provided, a default name will be used in the reports/ directory.")

    args = parser.parse_args()

    # Validate template file
    if not args.template_file:
        print("Error: --template-file is required", file=sys.stderr)
        sys.exit(1)

    try:
        # Initialize AWS session with profile if provided
        session_params = {}
        if args.profile:
            session_params["profile_name"] = args.profile
        
        # Handle AWS profile selection if not provided and in interactive mode
        if not args.profile:
            # First try to get the default profile from Boto3
            default_boto_profile = boto3.Session().profile_name
            if default_boto_profile:
                args.profile = default_boto_profile
                session_params["profile_name"] = args.profile
                print(f"Info: Auto-selected AWS Profile from Boto3 default: {args.profile}")
            # If no default profile was found and not in non-interactive mode
            elif not args.non_interactive:
                available_profiles = get_aws_profiles()
                # If exactly one profile is available, use it automatically
                if len(available_profiles) == 1:
                    args.profile = available_profiles[0]
                    session_params["profile_name"] = args.profile
                    print(f"Info: Auto-selected single available AWS Profile: {args.profile}")
                # If multiple profiles are available, prompt the user
                elif len(available_profiles) > 1:
                    print("\nAvailable AWS profiles:")
                    for i, profile in enumerate(available_profiles, 1):
                        print(f"  {i}. {profile}")
                    
                    profile_input = prompt_user("Select a profile number or press Enter to use the default profile", "default")
                    
                    if profile_input != "default":
                        try:
                            profile_index = int(profile_input) - 1
                            if 0 <= profile_index < len(available_profiles):
                                args.profile = available_profiles[profile_index]
                                session_params["profile_name"] = args.profile
                            else:
                                print(f"Invalid profile number. Using default profile.", file=sys.stderr)
                        except ValueError:
                            print(f"Invalid input. Using default profile.", file=sys.stderr)
        
        # Initialize region if provided
        if args.region:
            session_params["region_name"] = args.region
            
        # Create session and clients
        try:
            session = boto3.Session(**session_params)
        except ProfileNotFound:
            print(f"Error: AWS profile '{args.profile}' not found. Using default profile.", file=sys.stderr)
            session = boto3.Session()
            
        # Get region interactively if not provided
        if not args.region:
            session_region = session.region_name
            if session_region:
                args.region = session_region
                print(f"Info: Auto-selected AWS Region from environment/config: {args.region}")
            elif not args.non_interactive:
                regions = [
                    "us-east-1", "us-east-2", "us-west-1", "us-west-2",
                    "eu-west-1", "eu-west-2", "eu-west-3", "eu-central-1",
                    "ap-northeast-1", "ap-northeast-2", "ap-southeast-1", "ap-southeast-2",
                    "sa-east-1", "ca-central-1"
                ]
                print("\nAvailable AWS regions:")
                for i, region in enumerate(regions, 1):
                    print(f"  {i}. {region}")
                
                region_input = prompt_user("Select a region number or enter a region name", "us-east-1")
                
                try:
                    region_index = int(region_input) - 1
                    if 0 <= region_index < len(regions):
                        args.region = regions[region_index]
                    else:
                        args.region = region_input
                except ValueError:
                    args.region = region_input
            else:
                args.region = "us-east-1"
                
        # Create clients with the selected region
        iam_client = session.client("iam", region_name=args.region)
        sts_client = session.client("sts", region_name=args.region)
        print(f"Using AWS region: {args.region}")
        
        # Get AWS account ID
        account_id = get_aws_account_id(sts_client)
        
        # Get deploying principal ARN if not provided
        if not args.deploying_principal_arn:
            try:
                identity = get_current_identity(session)
                args.deploying_principal_arn = identity["Arn"]
                print(f"Info: Auto-determined Deploying Principal ARN: {args.deploying_principal_arn}")
            except AWSError:
                if args.non_interactive:
                    print("Error: Could not determine AWS identity and --deploying-principal-arn not provided", file=sys.stderr)
                    sys.exit(1)
                else:
                    args.deploying_principal_arn = prompt_user("Enter the ARN of the principal deploying the template")
                    if not args.deploying_principal_arn:
                        print("Error: Deploying principal ARN is required", file=sys.stderr)
                        sys.exit(1)
        
        # Validate ARN format
        if not args.deploying_principal_arn.startswith("arn:"):
            print(f"Error: Invalid principal ARN format: {args.deploying_principal_arn}", file=sys.stderr)
            sys.exit(1)
        
        # Get template parameters
        try:
            template_parameters = get_template_parameters(args.template_file)
        except Exception as e:
            print(f"Error loading template parameters: {e}", file=sys.stderr)
            sys.exit(1)

        # Parse and prompt for CloudFormation parameters
        cfn_cli_parameters = {}
        if args.parameters:
            for p_item in args.parameters:
                if "=" not in p_item:
                    raise InputError(f"Parameter '{p_item}' is not in Key=Value format.")
                key, value = p_item.split("=", 1)
                cfn_cli_parameters[key] = value
        
        # Process parameters that are not provided via CLI
        for param_name, param_def in template_parameters.items():
            if param_name not in cfn_cli_parameters:
                # If parameter has a default value in CFT, use it automatically
                if "Default" in param_def:
                    cfn_cli_parameters[param_name] = param_def["Default"]
                    print(f"Info: Using CFT default for Parameter {param_name}: {param_def['Default']}")
                # If no default and in interactive mode, handle special cases or prompt
                elif not args.non_interactive:
                    default_value = ""  # No CFT default, empty string for prompt
                    
                    # Special handling for OrganizationalUnitId
                    if param_name == "OrganizationalUnitId" and param_def.get("Type") == "String":
                        try:
                            ous = list_organizational_units(session)
                            # If exactly one OU is available, use it automatically
                            if len(ous) == 1:
                                cfn_cli_parameters[param_name] = ous[0]['Id']
                                print(f"Info: Auto-selected single available Organizational Unit: {ous[0]['Path']} (ID: {ous[0]['Id']})")
                            # If no OUs found but parameter has a default, use the default
                            elif not ous and "Default" in param_def:
                                cfn_cli_parameters[param_name] = param_def["Default"]
                                print(f"Info: Using CFT default for OrganizationalUnitId (no OUs found): {param_def['Default']}")
                            # If multiple OUs or no OUs and no default, prompt the user
                            elif ous:
                                print("\nAvailable Organizational Units:")
                                for i, ou in enumerate(ous, 1):
                                    print(f"  {i}. {ou['Path']} (ID: {ou['Id']})")
                                
                                ou_input = prompt_user("Select an OU number or enter an OU ID directly", default_value)
                                
                                try:
                                    ou_index = int(ou_input) - 1
                                    if 0 <= ou_index < len(ous):
                                        cfn_cli_parameters[param_name] = ous[ou_index]['Id']
                                    else:
                                        cfn_cli_parameters[param_name] = ou_input
                                except ValueError:
                                    cfn_cli_parameters[param_name] = ou_input
                            else:
                                # No OUs found or error listing them, prompt directly
                                cfn_cli_parameters[param_name] = prompt_user(
                                    f"Enter value for parameter '{param_name}' ({param_def.get('Description', '')})",
                                    default_value
                                )
                        except Exception as e:
                            print(f"Error listing organizational units: {e}", file=sys.stderr)
                            cfn_cli_parameters[param_name] = prompt_user(
                                f"Enter value for parameter '{param_name}' ({param_def.get('Description', '')})",
                                default_value
                            )
                    else:
                        # For other parameters, just prompt with description and default
                        cfn_cli_parameters[param_name] = prompt_user(
                            f"Enter value for parameter '{param_name}' ({param_def.get('Description', '')})",
                            default_value
                        )
                # If no default and in non-interactive mode, parameter will be missing
                # This will be handled by CloudFormation if the parameter is required
        
        # Parse condition values if provided
        condition_values = None
        if args.condition_values:
            try:
                condition_values = json.loads(args.condition_values)
                print(f"Using provided condition values: {condition_values}")
                
                # Validate condition values are booleans
                for key, value in condition_values.items():
                    if not isinstance(value, bool):
                        raise InputError(f"Condition value for '{key}' must be a boolean (true/false), got: {value}")
            except json.JSONDecodeError as e:
                raise InputError(f"Could not parse condition values JSON: {e}")
        
        # Print summary of parameters
        print("\nUsing CloudFormation parameters:")
        for key, value in cfn_cli_parameters.items():
            # Mask sensitive values like ExternalID
            if key in ["ExternalID"]:
                masked_value = value[:4] + "*" * (len(value) - 4) if len(value) > 4 else "****"
                print(f"  {key}: {masked_value}")
            else:
                print(f"  {key}: {value}")
        
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

        # Generate PDF report and IAM policy JSON by default unless --no-pdf is specified
        if not args.no_pdf:
            try:
                from report_generator import generate_pdf_report, update_task_status
                
                # Update task status if task file is provided
                task_file = os.environ.get("TASK_FILE")
                if task_file and os.path.exists(task_file):
                    update_task_status(task_file, "In Progress")
                
                # Generate PDF report and IAM policy JSON
                pdf_file, json_file = generate_pdf_report(
                    template_file=args.template_file,
                    principal_arn=args.deploying_principal_arn,
                    region=args.region,
                    actions=actions,
                    resource_arns=resource_arns,
                    prereq_checks=prerequisite_checks,
                    prereqs_ok=prereqs_ok,
                    permissions_ok=permissions_ok,
                    failed_simulations=failed_sims,
                    output_file=args.pdf_output
                )
                
                print(f"\nPDF report generated: {pdf_file}")
                if json_file:
                    print(f"IAM policy JSON generated: {json_file}")
                
                # Update task status if task file is provided
                if task_file and os.path.exists(task_file):
                    update_task_status(task_file, "Completed")
                
            except ImportError:
                print("\nError: Could not generate PDF report. WeasyPrint is required for PDF generation.")
                print("Install it with: pip install weasyprint")
                print("For more information, visit: https://doc.courtbouillon.org/weasyprint/stable/first_steps.html")
            except Exception as e:
                print(f"\nError generating PDF report: {e}", file=sys.stderr)
        
        if prereqs_ok and permissions_ok:
            print("\nPre-flight checks completed successfully.")
            sys.exit(0)
        else:
            print("\nPre-flight checks identified issues. Review failures before deploying.")
            
            # Note: IAM policy for missing permissions is now automatically included in the PDF report
            # when using the --generate-pdf flag
            
            sys.exit(1)
            
    except InputError as e:
        print(f"Input Error: {e}", file=sys.stderr)
        sys.exit(1)
    except AWSError as e:
        print(f"AWS Error: {e}", file=sys.stderr)
        sys.exit(1)
    except (PartialCredentialsError, NoCredentialsError) as e:
        print(f"AWS Credentials Error: {e}", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nOperation cancelled by user.", file=sys.stderr)
        sys.exit(130)
    except Exception as e:
        print(f"Unexpected Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()