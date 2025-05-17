#!/usr/bin/env python3
"""
CloudFormation Condition Evaluator.

This module provides functionality for evaluating CloudFormation conditions
based on input values or the template's Conditions block. It supports
condition evaluation for CloudFormation templates, including Fn::Equals
condition expressions and references to other conditions.
"""

import sys
from typing import Dict, Any

from value_resolver import resolve_value


def evaluate_condition(condition_name: str, context: Dict[str, Any]) -> bool:
    """
    Evaluate a CloudFormation condition based on input values or the template's Conditions block.
    
    This function handles condition evaluation for CloudFormation templates, supporting:
    1. Direct condition values provided as input
    2. Fn::Equals condition expressions
    3. References to other conditions
    
    Other condition functions (Fn::And, Fn::Or, Fn::Not, Fn::If) are recognized but
    not fully implemented yet, and will default to False with a warning.
    
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
                    left_value = resolve_value(equals_args[0], context["parameters"],
                                              context["account_id"], context["region"],
                                              resources)
                    right_value = resolve_value(equals_args[1], context["parameters"],
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