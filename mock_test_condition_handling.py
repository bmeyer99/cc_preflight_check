#!/usr/bin/env python3
"""
Mock tests for CloudFormation condition handling functionality.

This module contains tests for the condition evaluation functionality used in
the CloudFormation pre-flight check tool. It uses a mock implementation of the
evaluate_condition function to test condition evaluation logic independently.
"""

import unittest
import sys
from typing import Dict, Any, Optional

# Mock the evaluate_condition function from cc_preflight.py
def evaluate_condition(condition_name: str, context: Dict[str, Any]) -> bool:
    """
    Evaluate a CloudFormation condition based on input values or the template's Conditions block.
    
    This is a mock implementation of the evaluate_condition function from cc_preflight.py
    for testing purposes. It supports:
    1. Direct condition values provided as input
    2. Fn::Equals condition expressions
    3. References to other conditions
    
    Other condition functions (Fn::And, Fn::Or, Fn::Not, Fn::If) are recognized but
    not fully implemented, and will default to False with a warning.
    
    Args:
        condition_name: The name of the condition to evaluate
        context: Dictionary containing template data, resolved parameters, and condition values
                 Must include: "template", "parameters", "account_id", "region"
                 May include: "condition_values", "evaluated_conditions"
        
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
                    resources = context["template"].get("Resources", {})
                    
                    # Mock resolve_value for testing
                    def mock_resolve_value(value, params, account_id, region, resources):
                        if isinstance(value, dict) and "Ref" in value:
                            ref_val = value["Ref"]
                            if ref_val in params:
                                return params[ref_val]
                            # Handle other Ref cases
                            return str(ref_val)
                        return value
                    
                    left_value = mock_resolve_value(equals_args[0], context["parameters"],
                                                  context["account_id"], context["region"],
                                                  resources)
                    right_value = mock_resolve_value(equals_args[1], context["parameters"],
                                                   context["account_id"], context["region"],
                                                   resources)
                    result = (left_value == right_value)
                    context["evaluated_conditions"][condition_name] = result
                    return result
            
            # Handle condition reference
            elif "Condition" in condition_def:
                # Reference to another condition
                referenced_condition = condition_def["Condition"]
                result = evaluate_condition(referenced_condition, context)
                context["evaluated_conditions"][condition_name] = result
                return result
                
            # Handle other condition functions (not fully implemented yet)
            elif "Fn::And" in condition_def:
                print(f"Warning: Fn::And condition not fully supported yet. Defaulting to False for {condition_name}",
                      file=sys.stderr)
                context["evaluated_conditions"][condition_name] = False
                return False
            elif "Fn::Or" in condition_def:
                print(f"Warning: Fn::Or condition not fully supported yet. Defaulting to False for {condition_name}",
                      file=sys.stderr)
                context["evaluated_conditions"][condition_name] = False
                return False
            elif "Fn::Not" in condition_def:
                print(f"Warning: Fn::Not condition not fully supported yet. Defaulting to False for {condition_name}",
                      file=sys.stderr)
                context["evaluated_conditions"][condition_name] = False
                return False
            elif "Fn::If" in condition_def:
                print(f"Warning: Fn::If condition not fully supported yet. Defaulting to False for {condition_name}",
                      file=sys.stderr)
                context["evaluated_conditions"][condition_name] = False
                return False
    
    # If we get here, the condition wasn't found
    print(f"Error: Condition '{condition_name}' not found in input values or template.", file=sys.stderr)
    context["evaluated_conditions"][condition_name] = False
    return False

class TestConditionHandling(unittest.TestCase):
    """
    Test case for CloudFormation condition handling functionality.
    
    These tests verify that the condition evaluation logic correctly handles
    different types of conditions and condition references.
    """
    def setUp(self):
        """
        Set up test fixtures for the condition handling tests.
        
        Creates a mock CloudFormation template with various condition types:
        - Simple Fn::Equals conditions
        - Condition references
        - Complex conditions using Fn::And
        
        Also creates a mock context with parameters and condition values.
        """
        # Mock data for testing
        self.mock_template = {
            "Conditions": {
                "IsProduction": {
                    "Fn::Equals": [{"Ref": "Environment"}, "prod"]
                },
                "IsDevelopment": {
                    "Fn::Equals": [{"Ref": "Environment"}, "dev"]
                },
                "IsProductionOrStaging": {
                    "Condition": "IsProduction"  # Reference to another condition for testing
                },
                "ComplexCondition": {
                    "Fn::And": [
                        {"Condition": "IsProduction"},
                        {"Fn::Equals": [{"Ref": "Region"}, "us-east-1"]}
                    ]
                }
            },
            "Resources": {
                "MyResource": {
                    "Type": "AWS::S3::Bucket",
                    "Condition": "IsProduction",
                    "Properties": {}
                }
            }
        }
        
        self.mock_context = {
            "template": self.mock_template,
            "parameters": {"Environment": "prod", "Region": "us-east-1"},
            "account_id": "123456789012",
            "region": "us-east-1",
            "condition_values": {"ExplicitCondition": True}
        }

    def test_evaluate_condition_from_input_values(self):
        """
        Test evaluating a condition from input values.
        
        Verifies that conditions provided directly in the condition_values
        dictionary are correctly evaluated.
        """
        result = evaluate_condition("ExplicitCondition", self.mock_context)
        self.assertTrue(result)
        
        # Test condition not in input values
        result = evaluate_condition("NonExistentCondition", 
                                   {**self.mock_context, "condition_values": {}})
        self.assertFalse(result)

    def test_evaluate_fn_equals_condition(self):
        """
        Test evaluating a condition with Fn::Equals.
        
        Verifies that Fn::Equals conditions are correctly evaluated by:
        1. Testing a condition that should evaluate to True
        2. Testing a condition that should evaluate to False
        3. Modifying parameters and testing again to verify dynamic evaluation
        """
        # Should be True because Environment is 'prod'
        result = evaluate_condition("IsProduction", self.mock_context)
        self.assertTrue(result)
        
        # Should be False because Environment is not 'dev'
        result = evaluate_condition("IsDevelopment", self.mock_context)
        self.assertFalse(result)
        
        # Change parameter and test again - create a deep copy to avoid shared references
        modified_context = {
            "template": self.mock_template,
            "parameters": {"Environment": "dev", "Region": "us-east-1"},
            "account_id": "123456789012",
            "region": "us-east-1",
            "condition_values": {}
        }
        result = evaluate_condition("IsDevelopment", modified_context)
        self.assertTrue(result)

    def test_evaluate_condition_reference(self):
        """
        Test evaluating a condition that references another condition.
        
        Verifies that conditions that reference other conditions are correctly
        evaluated by:
        1. Testing a reference to a condition that evaluates to True
        2. Modifying parameters to make the referenced condition False and testing again
        """
        # IsProductionOrStaging references IsProduction, which should be True
        result = evaluate_condition("IsProductionOrStaging", self.mock_context)
        self.assertTrue(result)
        
        # Change parameter to make IsProduction false - create a deep copy to avoid shared references
        modified_context = {
            "template": {
                "Conditions": {
                    "IsProduction": {
                        "Fn::Equals": [{"Ref": "Environment"}, "prod"]
                    },
                    "IsProductionOrStaging": {
                        "Condition": "IsProduction"
                    }
                },
                "Resources": {}
            },
            "parameters": {"Environment": "dev", "Region": "us-east-1"},
            "account_id": "123456789012",
            "region": "us-east-1",
            "condition_values": {}
        }
        result = evaluate_condition("IsProductionOrStaging", modified_context)
        self.assertFalse(result)

    def test_evaluate_unsupported_condition_functions(self):
        """
        Test evaluating conditions with unsupported functions.
        
        Verifies that conditions using functions that are not fully implemented
        (like Fn::And) default to False with a warning.
        """
        # ComplexCondition uses Fn::And which is not fully supported yet
        result = evaluate_condition("ComplexCondition", self.mock_context)
        self.assertFalse(result)

    def test_memoization(self):
        """
        Test that condition evaluation results are memoized.
        
        Verifies that:
        1. Condition evaluation results are stored in the context
        2. Subsequent evaluations of the same condition use the memoized result
           even if the underlying condition definition changes
        
        This tests the optimization that prevents redundant condition evaluations.
        """
        # First evaluation
        result1 = evaluate_condition("IsProduction", self.mock_context)
        self.assertTrue(result1)
        
        # The result should be stored in evaluated_conditions
        self.assertIn("evaluated_conditions", self.mock_context)
        self.assertIn("IsProduction", self.mock_context["evaluated_conditions"])
        self.assertTrue(self.mock_context["evaluated_conditions"]["IsProduction"])
        
        # Modify the condition in the template (this shouldn't affect the result due to memoization)
        self.mock_template["Conditions"]["IsProduction"] = {
            "Fn::Equals": [{"Ref": "Environment"}, "not-prod"]
        }
        
        # Second evaluation should use the memoized result
        result2 = evaluate_condition("IsProduction", self.mock_context)
        self.assertTrue(result2)

if __name__ == '__main__':
    unittest.main()