#!/usr/bin/env python3
"""
Custom exceptions for the CloudFormation Pre-flight Check Tool.

This module defines a hierarchy of custom exceptions used throughout the tool
for better error handling and more specific error reporting.
"""


class CCPreflightError(Exception):
    """Base exception class for all cc_preflight errors."""
    pass


class TemplateError(CCPreflightError):
    """Exception raised for errors in the CloudFormation template."""
    pass


class InputError(CCPreflightError):
    """Exception raised for errors in user input."""
    pass


class AWSError(CCPreflightError):
    """Exception raised for AWS API errors."""
    pass


class ResourceError(CCPreflightError):
    """Exception raised for errors related to resources."""
    pass


class ValidationError(CCPreflightError):
    """Exception raised for validation errors."""
    pass