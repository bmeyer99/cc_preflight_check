#!/usr/bin/env python3
"""
CloudFormation Pre-flight Check Tool.

This module provides functionality to analyze CloudFormation templates
and simulate the IAM permissions required for deployment. It parses CloudFormation
templates, extracts required IAM actions based on resource types and properties,
constructs resource ARNs, and uses the AWS IAM policy simulator to verify if the
deploying principal has sufficient permissions.

Key features:
- CloudFormation template parsing with YAML tag handling
- Resource-to-IAM action mapping
- Resource name and ARN resolution
- Condition evaluation for conditional resources
- IAM permission simulation
- Prerequisite resource checking
"""

# This file has been modularized. It now serves as the main entry point
# and imports functionality from the following modules:
#
# - cc_preflight_exceptions.py: Custom exception classes
# - cfn_yaml_handler.py: YAML parsing and CloudFormation tag handling
# - aws_utils.py: AWS-related utility functions
# - condition_evaluator.py: CloudFormation condition evaluation
# - resource_processor.py: Resource name resolution and ARN construction
# - template_analyzer.py: Template parsing and action collection
# - iam_prerequisites.py: Prerequisite resource checking
# - iam_simulator.py: IAM permission simulation
# - cli_handler.py: Command-line interface handling

from cli_handler import main

if __name__ == "__main__":
    main()