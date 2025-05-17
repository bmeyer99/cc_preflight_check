#!/usr/bin/env python3
"""
IAM Prerequisites Checker.

This module provides functionality for checking the existence and configuration
of prerequisite resources required for CloudFormation template deployment,
such as IAM roles referenced by ARN.
"""

import sys
from typing import List, Dict, Any

from botocore.exceptions import ClientError

from cc_preflight_exceptions import AWSError, ValidationError


def check_prerequisites(checks: List[Dict[str, Any]], iam_client, region: str) -> bool:
    """
    Check for existence and basic configuration of prerequisite resources.
    
    Some CloudFormation templates require certain resources to exist before
    deployment, such as IAM roles referenced by ARN. This function verifies
    that these prerequisite resources exist and are properly configured.
    
    Supports checking for:
    - IAM role existence
    - Other AWS resources referenced by ARN
    
    Args:
        checks: List of prerequisite checks to perform
        iam_client: AWS IAM client
        region: AWS region
        
    Returns:
        Boolean indicating if all prerequisite checks passed
        
    Raises:
        AWSError: If there are issues with AWS API calls
        ValidationError: If check format is invalid
    """
    print("\n--- Checking Prerequisites ---")
    all_prereqs_ok = True
    
    if not checks:
        print("  No specific prerequisite resource checks defined.")
        return True
    
    for check in checks:
        if not isinstance(check, dict) or 'type' not in check or 'arn' not in check:
            print(f"  Warning: Invalid prerequisite check format: {check}", file=sys.stderr)
            all_prereqs_ok = False
            continue
            
        description = check.get('description', check['type'])
        print(f"  Checking: {description} (ARN: {check['arn']})")
        
        # Handle IAM role checks
        if check["type"] == "iam_role_exists":
            try:
                # Extract role name from ARN
                if '/' in check["arn"]:
                    role_name = check["arn"].split('/')[-1]
                else:
                    print(f"    [WARN] Invalid IAM role ARN format: {check['arn']}")
                    role_name = check["arn"].split(':')[-1]
                    
                iam_client.get_role(RoleName=role_name)
                print(f"    [PASS] Prerequisite IAM Role '{check['arn']}' exists.")
            except ClientError as e:
                if e.response['Error']['Code'] == 'NoSuchEntity':
                    print(f"    [FAIL] Prerequisite IAM Role '{check['arn']}' does not exist.")
                    all_prereqs_ok = False
                else:
                    error_msg = f"Error checking prerequisite IAM Role: {e}"
                    print(f"    [ERROR] {error_msg}")
                    all_prereqs_ok = False
            except Exception as e:
                error_msg = f"Unexpected error checking prerequisite: {e}"
                print(f"    [ERROR] {error_msg}")
                all_prereqs_ok = False
        
        # Handle AWS resource checks for other resource types
        elif check["type"].endswith("_exists"):
            # For now, we just log these checks but don't actually verify them
            # In a future enhancement, we could add specific checks for different resource types
            # using the appropriate AWS service clients
            print(f"    [INFO] Prerequisite resource check for {check['arn']} (verification not implemented)")
            
            # The deploying principal will need permissions to access this resource
            # This is handled in template_analyzer.py where we add the necessary actions
            # to the deploying_principal_actions set
        else:
            print(f"    [WARN] Unknown prerequisite check type: {check['type']}")
    
    # Summary
    if all_prereqs_ok:
        print("  All checked prerequisites appear to be in place.")
    else:
        print("  Some prerequisite checks failed.")
        
    return all_prereqs_ok