#!/usr/bin/env python3
"""
Test script for report generation.

This script demonstrates how to use the report generation functionality
by creating a sample PDF report and IAM policy JSON file with mock data.
"""

import os
import sys
import datetime
import json
import os
import argparse
from typing import Dict, List, Any

# Ensure the current directory is in the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from report_generator import generate_pdf_report
except ImportError:
    print("Error: Could not import report_generator module.")
    print("Make sure report_generator.py is in the current directory.")
    sys.exit(1)

def main():
    """
    Generate a sample PDF report and IAM policy JSON file with mock data.
    """
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Test report generation.")
    parser.add_argument("--pdf-output", help="Path to save the PDF report.")
    args = parser.parse_args()
    
    print("Generating sample reports...")
    
    # Mock data for testing
    template_file = "test_cfts/01_iam_role.yml"
    principal_arn = "arn:aws:iam::123456789012:user/test-user"
    region = "us-east-1"
    
    # Sample actions
    actions = [
        "iam:CreateRole",
        "iam:PutRolePolicy",
        "iam:AttachRolePolicy",
        "iam:PassRole",
        "cloudformation:CreateStack"
    ]
    
    # Sample resource ARNs
    resource_arns = [
        "arn:aws:iam::123456789012:role/TestRole",
        "arn:aws:cloudformation:us-east-1:123456789012:stack/TestStack/*"
    ]
    
    # Sample prerequisite checks
    prereq_checks = [
        {
            "type": "iam_role_exists",
            "arn": "arn:aws:iam::123456789012:role/ExistingRole",
            "description": "Existing IAM Role"
        }
    ]
    
    # Sample failed simulations with multiple resources having the same actions
    # This will demonstrate the condensation feature
    failed_simulations = [
        {
            "EvalActionName": "iam:PassRole",
            "EvalResourceName": "arn:aws:iam::123456789012:role/TestRole1",
            "EvalDecision": "implicitly denied",
            "OrganizationsDecisionDetail": {"AllowedByOrganizations": False}
        },
        {
            "EvalActionName": "iam:PassRole",
            "EvalResourceName": "arn:aws:iam::123456789012:role/TestRole2",
            "EvalDecision": "implicitly denied",
            "OrganizationsDecisionDetail": {"AllowedByOrganizations": False}
        },
        {
            "EvalActionName": "cloudformation:CreateStack",
            "EvalResourceName": "arn:aws:cloudformation:us-east-1:123456789012:stack/TestStack1/*",
            "EvalDecision": "implicitly denied"
        },
        {
            "EvalActionName": "cloudformation:CreateStack",
            "EvalResourceName": "arn:aws:cloudformation:us-east-1:123456789012:stack/TestStack2/*",
            "EvalDecision": "implicitly denied"
        },
        {
            "EvalActionName": "s3:GetObject",
            "EvalResourceName": "arn:aws:s3:::test-bucket/file1.txt",
            "EvalDecision": "implicitly denied"
        }
    ]
    
    # Generate timestamp for output filename
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = args.pdf_output if args.pdf_output else f"sample_report_{timestamp}.pdf"
    
    # Note: We don't need to specify the reports/ directory here
    # as the report_generator will automatically save to reports/ if only a filename is provided
    
    try:
        # Generate the PDF report and IAM policy JSON
        pdf_file, json_file = generate_pdf_report(
            template_file=template_file,
            principal_arn=principal_arn,
            region=region,
            actions=actions,
            resource_arns=resource_arns,
            prereq_checks=prereq_checks,
            prereqs_ok=True,  # Assume prerequisites passed
            permissions_ok=False,  # Assume permissions failed
            failed_simulations=failed_simulations,
            output_file=output_file
        )
        
        print(f"Sample PDF report generated: {pdf_file}")
        
        # Verify the JSON file was created and contains valid content
        if json_file and os.path.exists(json_file):
            print(f"Sample IAM policy JSON generated: {json_file}")
            
            # Validate JSON content
            try:
                with open(json_file, 'r') as f:
                    policy = json.load(f)
                
                # Basic validation of the policy structure
                if (isinstance(policy, dict) and
                    policy.get("Version") == "2012-10-17" and
                    isinstance(policy.get("Statement"), list)):
                    
                    # Check if the policy is properly structured with correct resource types
                    cloudformation_actions_correct = True
                    passrole_actions_correct = True
                    
                    for statement in policy.get("Statement", []):
                        actions = statement.get("Action", [])
                        resource = statement.get("Resource")
                        
                        # Convert single action to list for consistent processing
                        if isinstance(actions, str):
                            actions = [actions]
                        
                        # Check CloudFormation actions
                        if any(action.startswith("cloudformation:") for action in actions):
                            # CloudFormation actions should use CloudFormation stack ARNs or "*"
                            if isinstance(resource, str):
                                if not (resource == "*" or resource.startswith("arn:aws:cloudformation:")):
                                    cloudformation_actions_correct = False
                            elif isinstance(resource, list):
                                for res in resource:
                                    if not (res == "*" or res.startswith("arn:aws:cloudformation:")):
                                        cloudformation_actions_correct = False
                        
                        # Check PassRole actions
                        if "iam:PassRole" in actions:
                            # PassRole actions should use IAM role ARNs
                            if isinstance(resource, str):
                                if not resource.startswith("arn:aws:iam:") and resource != "*":
                                    passrole_actions_correct = False
                            elif isinstance(resource, list):
                                for res in resource:
                                    if not res.startswith("arn:aws:iam:") and res != "*":
                                        passrole_actions_correct = False
                    
                    if cloudformation_actions_correct and passrole_actions_correct:
                        print("IAM policy JSON validation: PASSED (Correct resource types for actions verified)")
                    else:
                        if not cloudformation_actions_correct:
                            print("IAM policy JSON validation: FAILED - CloudFormation actions not associated with correct resources")
                        if not passrole_actions_correct:
                            print("IAM policy JSON validation: FAILED - PassRole actions not associated with correct resources")
                    
                    # Print the policy for demonstration
                    print("\nGenerated IAM Policy:")
                    print(json.dumps(policy, indent=2))
                    
                    # Additional validation for condensed format
                    print("\nPolicy Condensation Analysis:")
                    
                    # Count total statements
                    total_statements = len(policy.get("Statement", []))
                    print(f"Total statements: {total_statements}")
                    
                    # Count resources and actions
                    total_resources = 0
                    total_actions = 0
                    for statement in policy.get("Statement", []):
                        if isinstance(statement.get("Resource"), list):
                            total_resources += len(statement.get("Resource", []))
                        else:
                            total_resources += 1
                        
                        if isinstance(statement.get("Action"), list):
                            total_actions += len(statement.get("Action", []))
                        else:
                            total_actions += 1
                    
                    print(f"Total resources: {total_resources}")
                    print(f"Total actions: {total_actions}")
                    
                    # Calculate condensation ratio
                    if total_resources > total_statements:
                        condensation_ratio = (total_resources - total_statements) / total_resources
                        print(f"Condensation ratio: {condensation_ratio:.2%}")
                        print("(Higher percentage indicates more effective grouping)")
                else:
                    print("IAM policy JSON validation: FAILED - Invalid policy structure")
            except json.JSONDecodeError:
                print("IAM policy JSON validation: FAILED - Invalid JSON format")
            except Exception as e:
                print(f"IAM policy JSON validation: FAILED - {e}")
        else:
            print("IAM policy JSON was not generated")
        
    except Exception as e:
        print(f"Error generating PDF report: {e}")
        print("\nNote: WeasyPrint is required for PDF generation.")
        print("Install it with: pip install weasyprint")
        print("For more information, visit: https://doc.courtbouillon.org/weasyprint/stable/first_steps.html")
        sys.exit(1)

if __name__ == "__main__":
    main()