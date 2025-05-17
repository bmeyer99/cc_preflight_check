#!/usr/bin/env python3
"""
Test script for PDF report generation.

This script demonstrates how to use the PDF report generation functionality
by creating a sample report with mock data.
"""

import os
import sys
import datetime
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
    Generate a sample PDF report with mock data.
    """
    print("Generating sample PDF report...")
    
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
    
    # Sample failed simulations
    failed_simulations = [
        {
            "EvalActionName": "iam:PassRole",
            "EvalResourceName": "arn:aws:iam::123456789012:role/TestRole",
            "EvalDecision": "implicitly denied",
            "OrganizationsDecisionDetail": {"AllowedByOrganizations": False}
        },
        {
            "EvalActionName": "cloudformation:CreateStack",
            "EvalResourceName": "arn:aws:cloudformation:us-east-1:123456789012:stack/TestStack/*",
            "EvalDecision": "implicitly denied"
        }
    ]
    
    # Generate timestamp for output filename
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = f"sample_report_{timestamp}.pdf"
    
    # Note: We don't need to specify the reports/ directory here
    # as the report_generator will automatically save to reports/ if only a filename is provided
    
    try:
        # Generate the PDF report
        pdf_file = generate_pdf_report(
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
        print("You can open this file to view the report.")
        
    except Exception as e:
        print(f"Error generating PDF report: {e}")
        print("\nNote: WeasyPrint is required for PDF generation.")
        print("Install it with: pip install weasyprint")
        print("For more information, visit: https://doc.courtbouillon.org/weasyprint/stable/first_steps.html")
        sys.exit(1)

if __name__ == "__main__":
    main()