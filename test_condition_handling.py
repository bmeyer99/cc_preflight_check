#!/usr/bin/env python3
import unittest
from cc_preflight import evaluate_condition

class TestConditionHandling(unittest.TestCase):
    def setUp(self):
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
        """Test evaluating a condition from input values"""
        result = evaluate_condition("ExplicitCondition", self.mock_context)
        self.assertTrue(result)
        
        # Test condition not in input values
        result = evaluate_condition("NonExistentCondition", 
                                   {**self.mock_context, "condition_values": {}})
        self.assertFalse(result)

    def test_evaluate_fn_equals_condition(self):
        """Test evaluating a condition with Fn::Equals"""
        # Should be True because Environment is 'prod'
        result = evaluate_condition("IsProduction", self.mock_context)
        self.assertTrue(result)
        
        # Should be False because Environment is not 'dev'
        result = evaluate_condition("IsDevelopment", self.mock_context)
        self.assertFalse(result)
        
        # Change parameter and test again
        modified_context = {**self.mock_context, "parameters": {"Environment": "dev", "Region": "us-east-1"}}
        result = evaluate_condition("IsDevelopment", modified_context)
        self.assertTrue(result)

    def test_evaluate_condition_reference(self):
        """Test evaluating a condition that references another condition"""
        # IsProductionOrStaging references IsProduction, which should be True
        result = evaluate_condition("IsProductionOrStaging", self.mock_context)
        self.assertTrue(result)
        
        # Change parameter to make IsProduction false
        modified_context = {**self.mock_context, "parameters": {"Environment": "dev", "Region": "us-east-1"}}
        result = evaluate_condition("IsProductionOrStaging", modified_context)
        self.assertFalse(result)

    def test_evaluate_unsupported_condition_functions(self):
        """Test evaluating conditions with unsupported functions (should default to False)"""
        # ComplexCondition uses Fn::And which is not fully supported yet
        result = evaluate_condition("ComplexCondition", self.mock_context)
        self.assertFalse(result)

    def test_memoization(self):
        """Test that condition evaluation results are memoized"""
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