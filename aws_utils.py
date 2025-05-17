#!/usr/bin/env python3
"""
AWS Utility Functions.

This module provides utility functions for interacting with AWS services,
including identity management, account information retrieval, and
AWS Organizations functionality.
"""

import sys
from typing import Dict, List, Any, Optional

import boto3
from botocore.exceptions import ClientError, NoCredentialsError, PartialCredentialsError, ProfileNotFound

from cc_preflight_exceptions import AWSError


def get_aws_account_id(sts_client) -> str:
    """
    Get current AWS Account ID.
    
    Args:
        sts_client: AWS STS client
        
    Returns:
        AWS account ID
        
    Raises:
        AWSError: If account ID cannot be determined due to AWS API issues
    """
    try:
        return sts_client.get_caller_identity()["Account"]
    except (ClientError, NoCredentialsError, PartialCredentialsError) as e:
        error_msg = f"Could not determine AWS Account ID: {e}"
        print(f"Error: {error_msg}", file=sys.stderr)
        raise AWSError(error_msg)


def get_aws_profiles() -> List[str]:
    """
    Get a list of available AWS CLI profiles.
    
    Returns:
        List of profile names, or empty list if no profiles found
    """
    try:
        session = boto3.Session()
        return session.available_profiles
    except Exception:
        return []


def get_current_identity(session: boto3.Session) -> Dict[str, str]:
    """
    Get the current AWS identity information.
    
    Args:
        session: AWS boto3 session
        
    Returns:
        Dictionary with identity information (ARN, Account, UserId)
        
    Raises:
        AWSError: If identity cannot be determined
    """
    try:
        sts_client = session.client('sts')
        return sts_client.get_caller_identity()
    except (ClientError, NoCredentialsError, PartialCredentialsError) as e:
        error_msg = f"Could not determine AWS identity: {e}"
        print(f"Error: {error_msg}", file=sys.stderr)
        raise AWSError(error_msg)


def list_organizational_units(session: boto3.Session) -> List[Dict[str, str]]:
    """
    List organizational units in the AWS Organization.
    
    Args:
        session: AWS boto3 session
        
    Returns:
        List of dictionaries with OU information (Id, Name)
        
    Raises:
        AWSError: If OUs cannot be listed
    """
    try:
        org_client = session.client('organizations')
        
        # Get the root ID
        roots = org_client.list_roots()
        if not roots.get('Roots'):
            print("No organization roots found.", file=sys.stderr)
            return []
            
        root_id = roots['Roots'][0]['Id']
        
        # List OUs recursively
        all_ous = []
        
        def list_ous_for_parent(parent_id, path=""):
            ous = org_client.list_organizational_units_for_parent(ParentId=parent_id)
            for ou in ous.get('OrganizationalUnits', []):
                ou_path = f"{path}/{ou['Name']}" if path else ou['Name']
                all_ous.append({
                    'Id': ou['Id'],
                    'Name': ou['Name'],
                    'Path': ou_path
                })
                # Recursively list child OUs
                list_ous_for_parent(ou['Id'], ou_path)
        
        list_ous_for_parent(root_id)
        return all_ous
        
    except ClientError as e:
        if e.response['Error']['Code'] == 'AWSOrganizationsNotInUseException':
            print("AWS Organizations is not in use for this account.", file=sys.stderr)
            return []
        elif e.response['Error']['Code'] == 'AccessDeniedException':
            print("Access denied when trying to list organizational units.", file=sys.stderr)
            return []
        else:
            error_msg = f"Error listing organizational units: {e}"
            print(f"Error: {error_msg}", file=sys.stderr)
            raise AWSError(error_msg)
    except Exception as e:
        error_msg = f"Unexpected error listing organizational units: {e}"
        print(f"Error: {error_msg}", file=sys.stderr)
        return []