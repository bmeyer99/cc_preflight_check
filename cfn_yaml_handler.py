#!/usr/bin/env python3
"""
CloudFormation YAML Handler.

This module provides functionality for parsing CloudFormation templates with
proper handling of CloudFormation-specific YAML tags and intrinsic functions.
It includes custom constructors for YAML tags like !Ref, !GetAtt, !Sub, etc.,
and functions for loading and validating CloudFormation templates.
"""

import os
import yaml
import functools
from typing import Dict, Any

from cc_preflight_exceptions import TemplateError, ValidationError


# Define CloudFormation YAML tag handlers
def cfn_ref_constructor(loader, node):
    """
    Handle !Ref tags in CloudFormation templates.
    
    Converts YAML !Ref syntax to the equivalent {"Ref": value} dictionary format
    that CloudFormation uses internally.
    
    Args:
        loader: YAML loader instance
        node: YAML node representing the !Ref tag
        
    Returns:
        Dictionary with "Ref" key and appropriate value
    """
    return {"Ref": loader.construct_scalar(node)}


def cfn_getatt_constructor(loader, node):
    """
    Handle !GetAtt tags in CloudFormation templates.
    
    Supports both string format (!GetAtt Resource.Attribute) and
    sequence format (!GetAtt [Resource, Attribute]).
    
    Args:
        loader: YAML loader instance
        node: YAML node representing the !GetAtt tag
        
    Returns:
        Dictionary with "Fn::GetAtt" key and appropriate value list
    """
    if isinstance(node, yaml.ScalarNode):
        value = loader.construct_scalar(node)
        # Split on dot for the Resource.Attribute format
        return {"Fn::GetAtt": value.split('.')}
    elif isinstance(node, yaml.SequenceNode):
        value = loader.construct_sequence(node)
        return {"Fn::GetAtt": value}
    return {"Fn::GetAtt": ["", ""]}  # Fallback for unexpected formats


def cfn_sub_constructor(loader, node):
    """
    Handle !Sub tags in CloudFormation templates.
    
    Supports both string format and array format with variable map.
    
    Args:
        loader: YAML loader instance
        node: YAML node representing the !Sub tag
        
    Returns:
        Dictionary with "Fn::Sub" key and appropriate value
    """
    if isinstance(node, yaml.ScalarNode):
        return {"Fn::Sub": loader.construct_scalar(node)}
    elif isinstance(node, yaml.SequenceNode):
        return {"Fn::Sub": loader.construct_sequence(node)}
    return {"Fn::Sub": ""}  # Fallback for unexpected formats


def cfn_join_constructor(loader, node):
    """
    Handle !Join tags in CloudFormation templates.
    
    Args:
        loader: YAML loader instance
        node: YAML node representing the !Join tag
        
    Returns:
        Dictionary with "Fn::Join" key and appropriate value list
    """
    if isinstance(node, yaml.SequenceNode):
        return {"Fn::Join": loader.construct_sequence(node)}
    return {"Fn::Join": ["", []]}  # Fallback for unexpected formats


def cfn_base_constructor(tag_name):
    """
    Create a constructor for CloudFormation intrinsic functions.
    
    This is a factory function that creates constructors for various
    CloudFormation intrinsic functions like !Select, !Split, etc.
    
    Args:
        tag_name: The name of the intrinsic function (without "Fn::" prefix)
        
    Returns:
        A constructor function that handles the specific tag
    """
    def constructor(loader, node):
        if isinstance(node, yaml.ScalarNode):
            return {f"Fn::{tag_name}": loader.construct_scalar(node)}
        elif isinstance(node, yaml.SequenceNode):
            return {f"Fn::{tag_name}": loader.construct_sequence(node)}
        elif isinstance(node, yaml.MappingNode):
            return {f"Fn::{tag_name}": loader.construct_mapping(node)}
        return {f"Fn::{tag_name}": None}  # Fallback for unexpected formats
    return constructor


# Register CloudFormation YAML tag handlers
def register_yaml_constructors():
    """Register all CloudFormation YAML tag constructors with the YAML loaders."""
    # Register with SafeLoader
    yaml.SafeLoader.add_constructor('!Ref', cfn_ref_constructor)
    yaml.SafeLoader.add_constructor('!GetAtt', cfn_getatt_constructor)
    yaml.SafeLoader.add_constructor('!Sub', cfn_sub_constructor)
    yaml.SafeLoader.add_constructor('!Join', cfn_join_constructor)
    yaml.SafeLoader.add_constructor('!Select', cfn_base_constructor('Select'))
    yaml.SafeLoader.add_constructor('!Split', cfn_base_constructor('Split'))
    yaml.SafeLoader.add_constructor('!FindInMap', cfn_base_constructor('FindInMap'))
    yaml.SafeLoader.add_constructor('!If', cfn_base_constructor('If'))
    yaml.SafeLoader.add_constructor('!Equals', cfn_base_constructor('Equals'))
    yaml.SafeLoader.add_constructor('!And', cfn_base_constructor('And'))
    yaml.SafeLoader.add_constructor('!Or', cfn_base_constructor('Or'))
    yaml.SafeLoader.add_constructor('!Not', cfn_base_constructor('Not'))
    yaml.SafeLoader.add_constructor('!Base64', cfn_base_constructor('Base64'))
    yaml.SafeLoader.add_constructor('!Cidr', cfn_base_constructor('Cidr'))
    yaml.SafeLoader.add_constructor('!ImportValue', cfn_base_constructor('ImportValue'))

    # Try to register with CSafeLoader if available
    try:
        yaml.CSafeLoader.add_constructor('!Ref', cfn_ref_constructor)
        yaml.CSafeLoader.add_constructor('!GetAtt', cfn_getatt_constructor)
        yaml.CSafeLoader.add_constructor('!Sub', cfn_sub_constructor)
        yaml.CSafeLoader.add_constructor('!Join', cfn_join_constructor)
        yaml.CSafeLoader.add_constructor('!Select', cfn_base_constructor('Select'))
        yaml.CSafeLoader.add_constructor('!Split', cfn_base_constructor('Split'))
        yaml.CSafeLoader.add_constructor('!FindInMap', cfn_base_constructor('FindInMap'))
        yaml.CSafeLoader.add_constructor('!If', cfn_base_constructor('If'))
        yaml.CSafeLoader.add_constructor('!Equals', cfn_base_constructor('Equals'))
        yaml.CSafeLoader.add_constructor('!And', cfn_base_constructor('And'))
        yaml.CSafeLoader.add_constructor('!Or', cfn_base_constructor('Or'))
        yaml.CSafeLoader.add_constructor('!Not', cfn_base_constructor('Not'))
        yaml.CSafeLoader.add_constructor('!Base64', cfn_base_constructor('Base64'))
        yaml.CSafeLoader.add_constructor('!Cidr', cfn_base_constructor('Cidr'))
        yaml.CSafeLoader.add_constructor('!ImportValue', cfn_base_constructor('ImportValue'))
    except AttributeError:
        pass  # CSafeLoader not available


# Register constructors when module is imported
register_yaml_constructors()


# Cache for template loading
@functools.lru_cache(maxsize=8)
def _load_template(template_path: str) -> Dict[str, Any]:
    """
    Load and parse a CloudFormation template with caching.
    
    This function loads a CloudFormation template from a file and parses it
    into a Python dictionary. It uses caching to avoid reloading the same
    template multiple times, which is useful for performance optimization.
    
    The function attempts to use the C-based YAML loader (CSafeLoader) for
    better performance, falling back to the Python-based loader if necessary.
    
    Args:
        template_path: Path to the CloudFormation template file
        
    Returns:
        Parsed template as a dictionary
        
    Raises:
        TemplateError: If template file doesn't exist or has invalid syntax
        ValidationError: If template is missing required sections
    """
    # Check if file exists
    if not os.path.isfile(template_path):
        raise TemplateError(f"Template file not found: '{template_path}'")
    
    try:
        with open(template_path, 'r') as f:
            # Use C-based YAML loader if available for better performance
            try:
                # Try to use the C-based loader for better performance
                template = yaml.CSafeLoader(f).get_data()
            except AttributeError:
                # Fall back to the Python-based loader
                template = yaml.safe_load(f)
                
        # Validate template structure
        if not isinstance(template, dict):
            raise ValidationError("Template is not a valid CloudFormation template (not a dictionary)")
            
        # Check for required sections
        if "Resources" not in template or not template["Resources"]:
            raise ValidationError("Template is missing the 'Resources' section or it's empty")
            
        return template
    except yaml.YAMLError as e:
        raise TemplateError(f"Invalid YAML/JSON syntax in template: {e}")
    except Exception as e:
        raise TemplateError(f"Failed to load template: {e}")


def get_template_parameters(template_path: str) -> Dict[str, Dict[str, Any]]:
    """
    Extract parameters from a CloudFormation template.
    
    Args:
        template_path: Path to the CloudFormation template file
        
    Returns:
        Dictionary of parameter names to their definitions
        
    Raises:
        TemplateError: If template cannot be read or parsed
    """
    try:
        template = _load_template(template_path)
        return template.get("Parameters", {})
    except (TemplateError, ValidationError) as e:
        raise