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


def get_relevant_resource_arns(action: str, resource_arns: List[str]) -> List[str]:
    """
    Filter resource ARNs to only include those relevant to the specified action.
    
    Args:
        action: The IAM action (e.g., 'ec2:DescribeSnapshots', 'iam:PassRole')
        resource_arns: List of all resource ARNs
        
    Returns:
        List of resource ARNs relevant to the action's service, or ['*'] for global actions
    """
    # Extract service from action (e.g., 'ec2' from 'ec2:DescribeSnapshots')
    service = action.split(':')[0] if ':' in action else ''
    
    # Handle special cases for actions that typically use '*' as resource
    # This includes:
    # 1. Actions that operate at the service level (not on specific resources)
    # 2. Creation actions that create new resources (not operating on existing ones)
    # 3. List/Describe actions that return multiple resources
    global_service_actions = {
        # Services where all actions use '*'
        'cloudformation': True,  # All CloudFormation actions
        'sts': True,  # All STS actions
        
        # Services with specific actions that use '*'
        'apigateway': ['GET', 'POST', 'PUT', 'PATCH', 'DELETE'],
        'cloudwatch': ['PutMetricData', 'GetMetricStatistics', 'ListMetrics'],
        'dynamodb': ['ListTables', 'CreateTable'],
        'ec2': ['DescribeInstances', 'DescribeSecurityGroups', 'DescribeVpcs', 'DescribeSubnets',
                'DescribeRouteTables', 'DescribeNetworkInterfaces', 'CreateSecurityGroup',
                'CreateVpc', 'CreateSubnet', 'CreateRouteTable', 'CreateNetworkInterface'],
        'ecr': ['GetAuthorizationToken', 'DescribeRepositories', 'CreateRepository'],
        'ecs': ['ListClusters', 'ListServices', 'CreateCluster', 'CreateService'],
        'events': ['PutRule', 'ListRules', 'DescribeRule'],
        'iam': ['GetUser', 'ListUsers', 'ListRoles', 'GetAccountSummary', 'CreateRole',
                'CreatePolicy', 'CreateUser', 'ListPolicies', 'ListGroups', 'CreateGroup'],
        'kms': ['CreateKey', 'ListKeys', 'ListAliases', 'CreateAlias', 'CreateGrant'],
        'lambda': ['ListFunctions', 'CreateFunction', 'GetAccountSettings'],
        'logs': ['CreateLogGroup', 'CreateLogStream', 'DescribeLogGroups', 'DescribeLogStreams'],
        'rds': ['DescribeDBInstances', 'DescribeDBClusters', 'CreateDBInstance', 'CreateDBCluster'],
        's3': ['ListAllMyBuckets', 'CreateBucket', 'ListBuckets'],
        'sns': ['CreateTopic', 'ListTopics', 'ListSubscriptions', 'SetSubscriptionAttributes', 'Unsubscribe'],
        'sqs': ['CreateQueue', 'ListQueues', 'GetQueueUrl'],
    }
    
    # Common action prefixes that typically use '*' as resource
    global_action_prefixes = {
        'Create': True,  # Creation actions typically use '*'
        'List': True,    # List actions typically use '*'
        'Describe': True, # Describe actions typically use '*'
    }
    
    # Check if this is a global action
    is_global_action = False
    
    # Check if the entire service is global
    if service in global_service_actions and isinstance(global_service_actions[service], bool):
        is_global_action = global_service_actions[service]
    # Check if the specific action is in the list for this service
    elif service in global_service_actions and ':' in action:
        action_name = action.split(':')[1]
        is_global_action = action_name in global_service_actions[service]
    # Check if the action starts with a global prefix (Create, List, Describe)
    elif ':' in action:
        action_name = action.split(':')[1]
        for prefix in global_action_prefixes:
            if action_name.startswith(prefix) and global_action_prefixes[prefix]:
                is_global_action = True
                break
    
    if is_global_action:
        return ['*']
    
    # Filter resource ARNs by service
    relevant_arns = []
    
    # Handle special case for iam:PassRole which applies to IAM role ARNs
    if action == 'iam:PassRole':
        for arn in resource_arns:
            if arn.startswith('arn:aws:iam:') and ':role/' in arn:
                relevant_arns.append(arn)
        return relevant_arns if relevant_arns else ['*']
    
    # For regular service actions, filter ARNs by service prefix
    arn_prefix = f'arn:aws:{service}:'
    for arn in resource_arns:
        if arn.startswith(arn_prefix):
            relevant_arns.append(arn)
    
    # If no relevant ARNs found, use '*' as a fallback
    # This handles cases where the template might not include resources of this service type
    # but the action still needs to be simulated
    return relevant_arns if relevant_arns else ['*']


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
            action_resources = get_relevant_resource_arns(action, resource_arns)
            
            # Log the resources being used for this action
            if len(action_resources) == 1 and action_resources[0] == '*':
                print(f"    Using Resource: '*' for action: {action}")
            elif len(action_resources) <= 3:  # Only show all ARNs if there are 3 or fewer
                print(f"    Using {len(action_resources)} Resources for action {action}: {action_resources}")
            else:
                print(f"    Using {len(action_resources)} Resources for action {action} (showing first 2): {action_resources[:2]} ...")
            
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