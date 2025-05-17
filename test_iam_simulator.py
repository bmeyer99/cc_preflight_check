#!/usr/bin/env python3
"""
Unit tests for IAM Simulator.

This module tests the IAM permission simulation functionality, ensuring that
different action types are simulated against the appropriate resources.
"""

import unittest
from unittest.mock import patch, MagicMock
import sys
import os

# Ensure the current directory is in the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from iam_simulator import simulate_iam_permissions


class TestIAMSimulator(unittest.TestCase):
    """Test cases for IAM Simulator functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_iam_client = MagicMock()
        self.principal_arn = "arn:aws:iam::123456789012:user/test-user"
        
        # Mock successful simulation response
        self.mock_iam_client.simulate_principal_policy.return_value = {
            'EvaluationResults': [
                {
                    'EvalActionName': 'test:Action',
                    'EvalDecision': 'allowed',
                    'EvalResourceName': 'test-resource'
                }
            ]
        }

    def test_cloudformation_actions_use_star_resource(self):
        """Test that CloudFormation actions are simulated against '*' as the resource."""
        actions = ["cloudformation:CreateStack", "cloudformation:DescribeStacks"]
        resource_arns = ["arn:aws:iam::123456789012:role/TestRole"]
        
        # Call the function
        simulate_iam_permissions(self.mock_iam_client, self.principal_arn, actions, resource_arns)
        
        # Check that the IAM client was called with the correct parameters
        calls = self.mock_iam_client.simulate_principal_policy.call_args_list
        
        # Verify each CloudFormation action was simulated with '*' as resource
        for i, action in enumerate(actions):
            call_args = calls[i][1]
            self.assertEqual(call_args['ActionNames'], [action])
            self.assertEqual(call_args['ResourceArns'], ["*"])

    def test_passrole_actions_use_role_arns(self):
        """Test that iam:PassRole actions are simulated against IAM role ARNs."""
        actions = ["iam:PassRole"]
        resource_arns = ["arn:aws:iam::123456789012:role/TestRole"]
        
        # Call the function
        simulate_iam_permissions(self.mock_iam_client, self.principal_arn, actions, resource_arns)
        
        # Check that the IAM client was called with the correct parameters
        call_args = self.mock_iam_client.simulate_principal_policy.call_args[1]
        self.assertEqual(call_args['ActionNames'], ["iam:PassRole"])
        self.assertEqual(call_args['ResourceArns'], resource_arns)

    def test_other_actions_use_provided_resources(self):
        """Test that other service actions are simulated against provided resources."""
        actions = ["s3:GetObject", "dynamodb:Query"]
        resource_arns = ["arn:aws:s3:::test-bucket/file.txt", "arn:aws:dynamodb:us-east-1:123456789012:table/TestTable"]
        
        # Call the function
        simulate_iam_permissions(self.mock_iam_client, self.principal_arn, actions, resource_arns)
        
        # Check that the IAM client was called with the correct parameters
        calls = self.mock_iam_client.simulate_principal_policy.call_args_list
        
        # Verify each action was simulated with the provided resources
        for i, action in enumerate(actions):
            call_args = calls[i][1]
            self.assertEqual(call_args['ActionNames'], [action])
            self.assertEqual(call_args['ResourceArns'], resource_arns)

    def test_mixed_actions_use_appropriate_resources(self):
        """Test that mixed action types are simulated against appropriate resources."""
        actions = [
            "cloudformation:CreateStack",
            "iam:PassRole",
            "s3:GetObject"
        ]
        resource_arns = [
            "arn:aws:iam::123456789012:role/TestRole",
            "arn:aws:s3:::test-bucket/file.txt"
        ]
        
        # Call the function
        simulate_iam_permissions(self.mock_iam_client, self.principal_arn, actions, resource_arns)
        
        # Check that the IAM client was called with the correct parameters
        calls = self.mock_iam_client.simulate_principal_policy.call_args_list
        
        # Verify CloudFormation action was simulated with '*' as resource
        cf_call_args = calls[0][1]
        self.assertEqual(cf_call_args['ActionNames'], ["cloudformation:CreateStack"])
        self.assertEqual(cf_call_args['ResourceArns'], ["*"])
        
        # Verify PassRole action was simulated with IAM role ARNs
        passrole_call_args = calls[1][1]
        self.assertEqual(passrole_call_args['ActionNames'], ["iam:PassRole"])
        self.assertEqual(passrole_call_args['ResourceArns'], resource_arns)
        
        # Verify S3 action was simulated with provided resources
        s3_call_args = calls[2][1]
        self.assertEqual(s3_call_args['ActionNames'], ["s3:GetObject"])
        self.assertEqual(s3_call_args['ResourceArns'], resource_arns)


if __name__ == '__main__':
    unittest.main()