#!/usr/bin/env python3
"""
IAM Permission Simulator.

This module provides functionality for simulating IAM permissions to verify
if a principal has the necessary permissions to perform specific actions on
specific resources. It uses the AWS IAM Policy Simulator API to check permissions
without actually performing the operations.
"""

import sys
from typing import Dict, List, Tuple, Any, Optional

from botocore.exceptions import ClientError

from cc_preflight_exceptions import AWSError, ValidationError


def simulate_iam_permissions(iam_client, principal_arn: str, actions: List[str],
                              resource_arns: List[str],
                              context_entries: Optional[List[Dict[str, Any]]] = None) -> Tuple[bool, List[Dict[str, Any]]]:
    """
    Simulate IAM permissions for the given principal, actions, and resources.
    
    This function uses the AWS IAM Policy Simulator API to check if the specified
    principal (user, role, or group) has the necessary permissions to perform
    the required actions on the specified resources. This allows for pre-flight
    validation of permissions without actually attempting the operations.
    
    The function handles:
    - Simulating each action individually to avoid compatibility issues
    - Processing and displaying the results
    - Identifying specific reasons for permission denials (e.g., SCPs, permission boundaries)
    
    Note: This function only simulates permissions needed by the deploying principal,
    not permissions needed by resources created within the stack. The deploying principal
    needs permissions to:
    1. Create and manage the CloudFormation stack
    2. Pass roles to services (iam:PassRole)
    3. Access prerequisite resources that already exist
    
    Args:
        iam_client: AWS IAM client
        principal_arn: ARN of the principal to simulate permissions for
        actions: List of IAM actions to simulate (only deploying principal actions)
        resource_arns: List of resource ARNs to simulate against
        context_entries: Optional list of context entries for the simulation
                        (e.g., for condition keys like aws:RequestTag)
        
    Returns:
        Tuple containing:
        - Boolean indicating if all actions are allowed
        - List of failed simulation results
        
    Raises:
        AWSError: If there are issues with AWS API calls
        ValidationError: If input parameters are invalid
    """
    print("\n--- Simulating IAM Permissions for Deploying Principal ---")
    
    # Validate inputs
    if not principal_arn or not principal_arn.startswith("arn:"):
        raise ValidationError(f"Invalid principal ARN format: {principal_arn}")
    
    print(f"  Principal ARN for Simulation: {principal_arn}")
    print(f"  Actions to Simulate ({len(actions)}): {actions}")
    print(f"  Resource ARNs for Simulation ({len(resource_arns)}): {resource_arns if resource_arns else ['*']}")
    print(f"  Note: Only simulating permissions needed by the deploying principal, not resources created by the template")

    # Skip simulation if no actions to simulate
    if not actions:
        print("  No actions to simulate. Skipping IAM simulation.")
        return True, []
    
    # Use '*' if no resource ARNs provided
    if not resource_arns:
        resource_arns = ['*']
    
    try:
        # Due to compatibility issues between different action types,
        # we'll simulate each action individually
        all_allowed = True
        all_failed_simulations = []
        
        # Process actions one by one
        print(f"  Processing {len(actions)} actions individually")
        
        # Group similar actions to reduce output verbosity
        action_groups = {}
        
        for i, action in enumerate(actions):
            # Show progress every 10 actions
            if i % 10 == 0:
                print(f"  Progress: {i}/{len(actions)} actions processed")
            
            # Determine appropriate resources based on action type
            action_resources = resource_arns
            
            # CloudFormation actions should use "*" as resource
            if action.startswith("cloudformation:"):
                action_resources = ["*"]
                print(f"    Using Resource: '*' for CloudFormation action: {action}")
            # Other actions use their specific resources
            
            # Prepare simulation input
            simulation_input = {
                'PolicySourceArn': principal_arn,
                'ActionNames': [action],
                'ResourceArns': action_resources
            }
            
            if context_entries:
                simulation_input['ContextEntries'] = context_entries
            
            try:
                # Run simulation for this action
                response = iam_client.simulate_principal_policy(**simulation_input)
                
                # Process results
                for eval_result in response.get('EvaluationResults', []):
                    eval_action_name = eval_result['EvalActionName']
                    eval_decision = eval_result['EvalDecision']
                    eval_resource_name = eval_result.get('EvalResourceName', '*')
                    
                    # Group by decision for more concise output
                    action_key = f"{eval_decision}:{eval_resource_name}"
                    if action_key not in action_groups:
                        action_groups[action_key] = {
                            'decision': eval_decision,
                            'resource': eval_resource_name,
                            'actions': []
                        }
                    action_groups[action_key]['actions'].append(eval_action_name)
                    
                    # Track failures
                    if eval_decision != "allowed":
                        all_allowed = False
                        all_failed_simulations.append(eval_result)
            except ClientError as e:
                print(f"    [WARN] Could not simulate action {action}: {e}")
                # Assume failure for actions that can't be simulated
                all_allowed = False
                all_failed_simulations.append({
                    'EvalActionName': action,
                    'EvalDecision': 'implicitly denied',
                    'EvalResourceName': '*',
                    'EvalDecisionDetails': [{'EvalDecisionType': 'Error', 'EvalDecisionMessage': str(e)}]
                })
        
        # Display grouped results
        print("\n  Simulation Results (Grouped):")
        for group_key, group_data in action_groups.items():
            decision = group_data['decision']
            resource = group_data['resource']
            actions_list = group_data['actions']
            
            decision_marker = "[PASS]" if decision == "allowed" else "[FAIL]"
            print(f"    {decision_marker} Resource: {resource}, Decision: {decision}")
            print(f"      Actions ({len(actions_list)}): {', '.join(actions_list[:5])}" +
                  (f" and {len(actions_list) - 5} more..." if len(actions_list) > 5 else ""))
            
            # Show denial reasons for failed groups
            if decision != "allowed" and len(all_failed_simulations) > 0:
                sample_failure = next((f for f in all_failed_simulations if f['EvalActionName'] in actions_list), None)
                if sample_failure:
                    if sample_failure.get('OrganizationsDecisionDetail', {}).get('AllowedByOrganizations') == False:
                        print(f"      Denied by: Organizations SCP")
                    if sample_failure.get('PermissionsBoundaryDecisionDetail', {}).get('AllowedByPermissionsBoundary') == False:
                        print(f"      Denied by: Permissions Boundary")
                    
                    # Categorize the permission type
                    action_name = sample_failure['EvalActionName']
                    if action_name.startswith("cloudformation:"):
                        print(f"      Permission Type: CloudFormation Stack Management")
                    elif action_name == "iam:PassRole":
                        print(f"      Permission Type: IAM Role Passing")
                    else:
                        print(f"      Permission Type: Prerequisite Resource Access")

        # Summary
        if all_allowed:
            print("\n  [SUCCESS] All simulated actions are allowed for the deploying principal.")
        else:
            print("\n  [FAILURE] Some simulated actions were DENIED for the deploying principal. Review details above.")
            print("  Note: These are only the permissions needed by the deploying principal to manage the stack")
            print("        and access prerequisite resources, not permissions for resources created by the stack.")
        
        return all_allowed, all_failed_simulations

    except ClientError as e:
        error_msg = f"IAM simulation failed: {e}"
        print(f"  [ERROR] {error_msg}", file=sys.stderr)
        if "InvalidInput" in str(e):
            raise ValidationError(f"Invalid input for IAM simulation: {e}")
        elif "AccessDenied" in str(e):
            raise AWSError(f"Access denied when attempting IAM simulation. Ensure your credentials have iam:SimulatePrincipalPolicy permission.")
        else:
            raise AWSError(error_msg)
    except Exception as e:
        error_msg = f"An unexpected error occurred during IAM simulation: {e}"
        print(f"  [ERROR] {error_msg}", file=sys.stderr)
        raise AWSError(error_msg)