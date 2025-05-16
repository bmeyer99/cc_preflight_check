#!/usr/bin/env python3
import unittest
from value_resolver import resolve_value, PSEUDO_PARAMETER_RESOLUTIONS

class TestResolveValue(unittest.TestCase):
    def setUp(self):
        # Mock data for testing
        self.mock_parameters = {
            "ParamWithDefault": "DefaultValue",
            "ParamWithoutDefault": "ProvidedValue",
            "ComplexParam": {
                "Key": "Value"
            }
        }
        self.mock_resources = {
            "MyResource": {
                "Type": "AWS::SomeType",
                "Properties": {}
            }
        }
        self.account_id = "123456789012"
        self.region = "us-east-1"

    def test_simple_value(self):
        """Test resolving a simple string value"""
        value = "simple-string"
        result = resolve_value(value, self.mock_parameters, self.account_id, self.region, self.mock_resources)
        self.assertEqual(result, "simple-string")

    def test_ref_pseudo_parameter(self):
        """Test resolving AWS pseudo parameters"""
        value = {"Ref": "AWS::AccountId"}
        result = resolve_value(value, self.mock_parameters, self.account_id, self.region, self.mock_resources)
        self.assertEqual(result, PSEUDO_PARAMETER_RESOLUTIONS["AWS::AccountId"])

    def test_ref_template_parameter(self):
        """Test resolving template parameter references"""
        value = {"Ref": "ParamWithDefault"}
        result = resolve_value(value, self.mock_parameters, self.account_id, self.region, self.mock_resources)
        self.assertEqual(result, "DefaultValue")

    def test_ref_resource(self):
        """Test resolving resource references"""
        value = {"Ref": "MyResource"}
        result = resolve_value(value, self.mock_parameters, self.account_id, self.region, self.mock_resources)
        self.assertEqual(result, "arn:aws:::resolved-ref-myresource")

    def test_ref_unresolved(self):
        """Test handling of unresolved references"""
        value = {"Ref": "NonExistentParam"}
        result = resolve_value(value, self.mock_parameters, self.account_id, self.region, self.mock_resources)
        self.assertEqual(result, "UNRESOLVED_REF_FOR_NonExistentParam")

    def test_sub_simple(self):
        """Test resolving simple Fn::Sub expressions"""
        value = {"Fn::Sub": "prefix-${AWS::Region}-suffix"}
        result = resolve_value(value, self.mock_parameters, self.account_id, self.region, self.mock_resources)
        self.assertEqual(result, f"prefix-{PSEUDO_PARAMETER_RESOLUTIONS['AWS::Region']}-suffix")

    def test_sub_with_parameter(self):
        """Test resolving Fn::Sub with parameter references"""
        value = {"Fn::Sub": "prefix-${ParamWithDefault}-suffix"}
        result = resolve_value(value, self.mock_parameters, self.account_id, self.region, self.mock_resources)
        self.assertEqual(result, "prefix-DefaultValue-suffix")

    def test_sub_with_resource(self):
        """Test resolving Fn::Sub with resource references"""
        value = {"Fn::Sub": "prefix-${MyResource}-suffix"}
        result = resolve_value(value, self.mock_parameters, self.account_id, self.region, self.mock_resources)
        self.assertEqual(result, "prefix-arn:aws:::resolved-sub-myresource-suffix")

    def test_sub_unresolved(self):
        """Test handling of unresolved Fn::Sub variables"""
        value = {"Fn::Sub": "prefix-${NonExistentVar}-suffix"}
        result = resolve_value(value, self.mock_parameters, self.account_id, self.region, self.mock_resources)
        self.assertEqual(result, "prefix-UNRESOLVED_SUB_VAR_NonExistentVar-suffix")

    def test_join(self):
        """Test resolving Fn::Join expressions"""
        value = {"Fn::Join": ["-", ["part1", {"Ref": "AWS::Region"}, "part2"]]}
        result = resolve_value(value, self.mock_parameters, self.account_id, self.region, self.mock_resources)
        self.assertEqual(result, f"part1-{PSEUDO_PARAMETER_RESOLUTIONS['AWS::Region']}-part2")

    def test_nested_functions(self):
        """Test resolving nested function calls"""
        value = {
            "Fn::Join": [
                "-",
                [
                    {"Ref": "AWS::AccountId"},
                    {"Fn::Sub": "prefix-${ParamWithDefault}"}
                ]
            ]
        }
        result = resolve_value(value, self.mock_parameters, self.account_id, self.region, self.mock_resources)
        self.assertEqual(result, f"{PSEUDO_PARAMETER_RESOLUTIONS['AWS::AccountId']}-prefix-DefaultValue")

    def test_get_att_basic(self):
        """Test basic handling of GetAtt function for unsupported resource types"""
        value = {"Fn::GetAtt": ["UnsupportedResource", "Arn"]}
        result = resolve_value(value, self.mock_parameters, self.account_id, self.region, self.mock_resources)
        self.assertEqual(result, "getatt:UnsupportedResource.Arn")
    
    def test_get_att_iam_role(self):
        """Test GetAtt for IAM Role Arn"""
        # Add an IAM Role to mock resources
        self.mock_resources["MyRole"] = {
            "Type": "AWS::IAM::Role",
            "Properties": {}
        }
        value = {"Fn::GetAtt": ["MyRole", "Arn"]}
        result = resolve_value(value, self.mock_parameters, self.account_id, self.region, self.mock_resources)
        self.assertEqual(result, f"arn:aws:iam::{self.account_id}:role/resolved-getatt-myrole-arn")
    
    def test_get_att_s3_bucket_domain_name(self):
        """Test GetAtt for S3 Bucket DomainName"""
        # Add an S3 Bucket to mock resources
        self.mock_resources["MyBucket"] = {
            "Type": "AWS::S3::Bucket",
            "Properties": {}
        }
        value = {"Fn::GetAtt": ["MyBucket", "DomainName"]}
        result = resolve_value(value, self.mock_parameters, self.account_id, self.region, self.mock_resources)
        self.assertEqual(result, "resolved-getatt-mybucket-domainname.s3.amazonaws.com")
    
    def test_get_att_lambda_function_arn(self):
        """Test GetAtt for Lambda Function Arn"""
        # Add a Lambda Function to mock resources
        self.mock_resources["MyFunction"] = {
            "Type": "AWS::Lambda::Function",
            "Properties": {}
        }
        value = {"Fn::GetAtt": ["MyFunction", "Arn"]}
        result = resolve_value(value, self.mock_parameters, self.account_id, self.region, self.mock_resources)
        self.assertEqual(result, f"arn:aws:lambda:{self.region}:{self.account_id}:function:resolved-getatt-myfunction-arn")
    
    def test_get_att_sqs_queue_url(self):
        """Test GetAtt for SQS Queue URL"""
        # Add an SQS Queue to mock resources
        self.mock_resources["MyQueue"] = {
            "Type": "AWS::SQS::Queue",
            "Properties": {}
        }
        value = {"Fn::GetAtt": ["MyQueue", "QueueUrl"]}
        result = resolve_value(value, self.mock_parameters, self.account_id, self.region, self.mock_resources)
        self.assertEqual(result, f"https://sqs.{self.region}.amazonaws.com/{self.account_id}/resolved-getatt-myqueue-queueurl")

    def test_aws_no_value(self):
        """Test handling of AWS::NoValue"""
        value = {"Ref": "AWS::NoValue"}
        result = resolve_value(value, self.mock_parameters, self.account_id, self.region, self.mock_resources)
        self.assertIsNone(result)

    def test_join_with_none(self):
        """Test Fn::Join handling of None values from AWS::NoValue"""
        value = {"Fn::Join": ["-", ["part1", {"Ref": "AWS::NoValue"}, "part2"]]}
        result = resolve_value(value, self.mock_parameters, self.account_id, self.region, self.mock_resources)
        self.assertEqual(result, "part1--part2")

if __name__ == '__main__':
    unittest.main()