import unittest
from value_resolver import resolve_value, PSEUDO_PARAMETER_RESOLUTIONS
from resource_map import RESOURCE_ACTION_MAP

class TestResolveValue(unittest.TestCase):

    def setUp(self):
        # Mock data for testing
        self.mock_parameters = {
            "ParamWithDefault": "DefaultValue",
            "ParamWithoutDefault": "PlaceholderForNoDefault", # In a real scenario, this might be None or handled differently before resolve_value
        }
        self.mock_resources = {
            "MyResource": {"Type": "AWS::Some::Resource"},
            "AnotherResource": {"Type": "AWS::Another::Resource"}
        }
        self.mock_account_id = "123456789012"
        self.mock_region = "us-east-1"
        # Use the actual pseudo-parameter resolutions from the source file
        self.mock_pseudo_parameters = PSEUDO_PARAMETER_RESOLUTIONS

    # --- Ref Resolution Tests ---

    def test_ref_parameter_with_default(self):
        value = {"Ref": "ParamWithDefault"}
        expected = "DefaultValue"
        result = resolve_value(value, self.mock_parameters, self.mock_account_id, self.mock_region, self.mock_resources)
        self.assertEqual(result, expected)

    def test_ref_parameter_without_default(self):
        # Note: The current resolve_value implementation returns the parameter value directly.
        # If a parameter without a default is not provided, it wouldn't be in mock_parameters.
        # The current implementation would then fall through to the "Unresolved Ref" case.
        # Let's test that behavior.
        value = {"Ref": "NonExistentParameter"}
        expected = "UNRESOLVED_REF_FOR_NonExistentParameter"
        result = resolve_value(value, self.mock_parameters, self.mock_account_id, self.mock_region, self.mock_resources)
        self.assertEqual(result, expected)

    def test_ref_logical_resource_id(self):
        value = {"Ref": "MyResource"}
        # The placeholder format is defined in resolve_value
        expected = "arn:aws:::resolved-ref-myresource"
        result = resolve_value(value, self.mock_parameters, self.mock_account_id, self.mock_region, self.mock_resources)
        self.assertEqual(result, expected)

    def test_ref_aws_partition_pseudo_parameter(self):
        value = {"Ref": "AWS::Partition"}
        expected = self.mock_pseudo_parameters["AWS::Partition"]
        result = resolve_value(value, self.mock_parameters, self.mock_account_id, self.mock_region, self.mock_resources)
        self.assertEqual(result, expected)

    def test_ref_aws_region_pseudo_parameter(self):
        value = {"Ref": "AWS::Region"}
        expected = self.mock_pseudo_parameters["AWS::Region"]
        result = resolve_value(value, self.mock_parameters, self.mock_account_id, self.mock_region, self.mock_resources)
        self.assertEqual(result, expected)

    def test_ref_aws_account_id_pseudo_parameter(self):
        value = {"Ref": "AWS::AccountId"}
        expected = self.mock_pseudo_parameters["AWS::AccountId"]
        result = resolve_value(value, self.mock_parameters, self.mock_account_id, self.mock_region, self.mock_resources)
        self.assertEqual(result, expected)

    def test_ref_aws_stack_name_pseudo_parameter(self):
        value = {"Ref": "AWS::StackName"}
        expected = self.mock_pseudo_parameters["AWS::StackName"]
        result = resolve_value(value, self.mock_parameters, self.mock_account_id, self.mock_region, self.mock_resources)
        self.assertEqual(result, expected)

    def test_ref_aws_stack_id_pseudo_parameter(self):
        value = {"Ref": "AWS::StackId"}
        expected = self.mock_pseudo_parameters["AWS::StackId"]
        result = resolve_value(value, self.mock_parameters, self.mock_account_id, self.mock_region, self.mock_resources)
        self.assertEqual(result, expected)

    def test_ref_aws_url_suffix_pseudo_parameter(self):
        value = {"Ref": "AWS::URLSuffix"}
        expected = self.mock_pseudo_parameters["AWS::URLSuffix"]
        result = resolve_value(value, self.mock_parameters, self.mock_account_id, self.mock_region, self.mock_resources)
        self.assertEqual(result, expected)

    def test_ref_aws_novalue_pseudo_parameter(self):
        value = {"Ref": "AWS::NoValue"}
        expected = self.mock_pseudo_parameters["AWS::NoValue"] # Should be None
        result = resolve_value(value, self.mock_parameters, self.mock_account_id, self.mock_region, self.mock_resources)
        self.assertIsNone(result)

    # --- Fn::Sub Resolution Tests (single string form) ---

    def test_sub_string_no_variables(self):
        value = {"Fn::Sub": "This is a plain string."}
        expected = "This is a plain string."
        result = resolve_value(value, self.mock_parameters, self.mock_account_id, self.mock_region, self.mock_resources)
        self.assertEqual(result, expected)

    def test_sub_string_with_parameter_reference(self):
        value = {"Fn::Sub": "The parameter value is ${ParamWithDefault}."}
        expected = "The parameter value is DefaultValue."
        result = resolve_value(value, self.mock_parameters, self.mock_account_id, self.mock_region, self.mock_resources)
        self.assertEqual(result, expected)

    def test_sub_string_with_resource_id_reference(self):
        value = {"Fn::Sub": "The resource ARN is ${MyResource}."}
        # The placeholder format is defined in resolve_value
        expected = "The resource ARN is arn:aws:::resolved-sub-myresource."
        result = resolve_value(value, self.mock_parameters, self.mock_account_id, self.mock_region, self.mock_resources)
        self.assertEqual(result, expected)

    def test_sub_string_with_aws_region_pseudo_parameter_reference(self):
        value = {"Fn::Sub": "The region is ${AWS::Region}."}
        expected = f"The region is {self.mock_pseudo_parameters['AWS::Region']}."
        result = resolve_value(value, self.mock_parameters, self.mock_account_id, self.mock_region, self.mock_resources)
        self.assertEqual(result, expected)

    def test_sub_string_with_multiple_references(self):
        value = {"Fn::Sub": "Account: ${AWS::AccountId}, Region: ${AWS::Region}, Param: ${ParamWithDefault}, Resource: ${MyResource}"}
        expected = f"Account: {self.mock_pseudo_parameters['AWS::AccountId']}, Region: {self.mock_pseudo_parameters['AWS::Region']}, Param: {self.mock_parameters['ParamWithDefault']}, Resource: arn:aws:::resolved-sub-myresource"
        result = resolve_value(value, self.mock_parameters, self.mock_account_id, self.mock_region, self.mock_resources)
        self.assertEqual(result, expected)

    def test_sub_string_with_literal_dollar(self):
        value = {"Fn::Sub": "This is a literal $$."}
        expected = "This is a literal $."
        result = resolve_value(value, self.mock_parameters, self.mock_account_id, self.mock_region, self.mock_resources)
        self.assertEqual(result, expected)

    def test_sub_string_with_undefined_variable(self):
        value = {"Fn::Sub": "String with ${UndefinedVar}."}
        # The chosen behavior in resolve_value is to use a placeholder
        expected = "String with UNRESOLVED_SUB_VAR_UndefinedVar."
        result = resolve_value(value, self.mock_parameters, self.mock_account_id, self.mock_region, self.mock_resources)
        self.assertEqual(result, expected)

    # --- Fn::Join Resolution Tests ---

    def test_join_list_of_literal_strings(self):
        value = {"Fn::Join": [":", ["string1", "string2", "string3"]]}
        expected = "string1:string2:string3"
        result = resolve_value(value, self.mock_parameters, self.mock_account_id, self.mock_region, self.mock_resources)
        self.assertEqual(result, expected)

    def test_join_list_containing_ref_parameter(self):
        value = {"Fn::Join": ["-", ["prefix", {"Ref": "ParamWithDefault"}, "suffix"]]}
        expected = "prefix-DefaultValue-suffix"
        result = resolve_value(value, self.mock_parameters, self.mock_account_id, self.mock_region, self.mock_resources)
        self.assertEqual(result, expected)

    def test_join_list_containing_ref_resource_id(self):
        value = {"Fn::Join": ["/", ["path", {"Ref": "MyResource"}, "details"]]}
        # The placeholder format is defined in resolve_value
        expected = "path/arn:aws:::resolved-ref-myresource/details"
        result = resolve_value(value, self.mock_parameters, self.mock_account_id, self.mock_region, self.mock_resources)
        self.assertEqual(result, expected)

    def test_join_list_containing_ref_aws_region(self):
        value = {"Fn::Join": [".", ["my-service", {"Ref": "AWS::Region"}, "amazonaws", {"Ref": "AWS::URLSuffix"}]]}
        expected = f"my-service.{self.mock_pseudo_parameters['AWS::Region']}.amazonaws.{self.mock_pseudo_parameters['AWS::URLSuffix']}"
        result = resolve_value(value, self.mock_parameters, self.mock_account_id, self.mock_region, self.mock_resources)
        self.assertEqual(result, expected)

    def test_join_list_containing_simple_sub(self):
        value = {"Fn::Join": ["_", ["part1", {"Fn::Sub": "part2-${ParamWithDefault}"}, "part3"]]}
        expected = "part1_part2-DefaultValue_part3"
        result = resolve_value(value, self.mock_parameters, self.mock_account_id, self.mock_region, self.mock_resources)
        self.assertEqual(result, expected)

    def test_join_list_with_mixed_items(self):
        value = {"Fn::Join": ["-", ["literal", {"Ref": "ParamWithDefault"}, {"Fn::Sub": "sub-${AWS::Region}"}, {"Ref": "MyResource"}, "end"]]}
        expected = f"literal-DefaultValue-sub-{self.mock_pseudo_parameters['AWS::Region']}-arn:aws:::resolved-ref-myresource-end"
        result = resolve_value(value, self.mock_parameters, self.mock_account_id, self.mock_region, self.mock_resources)
        self.assertEqual(result, expected)

    def test_join_empty_list(self):
        value = {"Fn::Join": [",", []]}
        expected = ""
        result = resolve_value(value, self.mock_parameters, self.mock_account_id, self.mock_region, self.mock_resources)
        self.assertEqual(result, expected)

    def test_join_list_with_single_item(self):
        value = {"Fn::Join": ["-", ["single_item"]]}
        expected = "single_item"
        result = resolve_value(value, self.mock_parameters, self.mock_account_id, self.mock_region, self.mock_resources)
        self.assertEqual(result, expected)

    def test_join_list_with_none_from_novalue(self):
        # Ensure None from AWS::NoValue is handled correctly (becomes empty string in join)
        value = {"Fn::Join": ["-", ["prefix", {"Ref": "AWS::NoValue"}, "suffix"]]}
        expected = "prefix--suffix" # None becomes empty string
        result = resolve_value(value, self.mock_parameters, self.mock_account_id, self.mock_region, self.mock_resources)
        self.assertEqual(result, expected)


    # --- Nested Intrinsic Function Tests ---

    def test_nested_sub_with_ref_parameter(self):
        # e.g., {"Fn::Sub": "arn:${AWS::Partition}:service:::${MyResourceNameParam}"} where MyResourceNameParam is a Ref to a parameter.
        # Mock a parameter that would be referenced within the Sub
        self.mock_parameters["MyResourceNameParam"] = "MySpecificResourceName"
        value = {"Fn::Sub": "arn:${AWS::Partition}:service:::${MyResourceNameParam}"}
        expected = f"arn:{self.mock_pseudo_parameters['AWS::Partition']}:service:::MySpecificResourceName"
        result = resolve_value(value, self.mock_parameters, self.mock_account_id, self.mock_region, self.mock_resources)
        self.assertEqual(result, expected)

    def test_nested_join_with_ref_and_sub(self):
        # e.g., {"Fn::Join": [":", [{"Ref": "Part1"}, {"Fn::Sub": "Part2-${AWS::Region}"}]]}
        # Mock a parameter that would be referenced in the Join list
        self.mock_parameters["Part1"] = "FirstPart"
        value = {"Fn::Join": [":", [{"Ref": "Part1"}, {"Fn::Sub": "Part2-${AWS::Region}"}]]}
        expected = f"FirstPart:Part2-{self.mock_pseudo_parameters['AWS::Region']}"
        result = resolve_value(value, self.mock_parameters, self.mock_account_id, self.mock_region, self.mock_resources)
        self.assertEqual(result, expected)

    # --- Plain String Value Test ---

    def test_plain_string_value(self):
        value = "This is just a string."
        expected = "This is just a string."
        result = resolve_value(value, self.mock_parameters, self.mock_account_id, self.mock_region, self.mock_resources)
        self.assertEqual(result, expected)

    # --- Test handling of lists and dictionaries containing resolvable values ---
    def test_list_with_resolvable_items(self):
        value = ["literal", {"Ref": "ParamWithDefault"}, {"Fn::Sub": "sub-${AWS::Region}"}]
        expected = ["literal", "DefaultValue", f"sub-{self.mock_pseudo_parameters['AWS::Region']}"]
        result = resolve_value(value, self.mock_parameters, self.mock_account_id, self.mock_region, self.mock_resources)
        self.assertEqual(result, expected)

    def test_dictionary_with_resolvable_values(self):
        value = {
            "Key1": "literal",
            "Key2": {"Ref": "ParamWithDefault"},
            "Key3": {"Fn::Sub": "sub-${AWS::Region}"},
            "Nested": {
                "NestedKey": {"Ref": "MyResource"}
            }
        }
        expected = {
            "Key1": "literal",
            "Key2": "DefaultValue",
            "Key3": f"sub-{self.mock_pseudo_parameters['AWS::Region']}",
            "Nested": {
                "NestedKey": "arn:aws:::resolved-ref-myresource"
            }
        }
        result = resolve_value(value, self.mock_parameters, self.mock_account_id, self.mock_region, self.mock_resources)
        self.assertEqual(result, expected)
class TestResourceActionMap(unittest.TestCase):

    def test_resource_action_map_structure(self):
        self.assertIsInstance(RESOURCE_ACTION_MAP, dict)
        for resource_type, resource_data in RESOURCE_ACTION_MAP.items():
            self.assertIsInstance(resource_data, dict, f"Value for {resource_type} is not a dictionary")
            if "operation_actions" in resource_data:
                self.assertIsInstance(resource_data["operation_actions"], dict, f"operation_actions for {resource_type} is not a dictionary")
                for operation, actions in resource_data["operation_actions"].items():
                    self.assertIsInstance(actions, list, f"Actions for {resource_type} operation {operation} is not a list")
                    for action in actions:
                        self.assertIsInstance(action, str, f"Action in list for {resource_type} operation {operation} is not a string")

    def test_key_resource_types_present(self):
        expected_resource_types = [
            "AWS::IAM::Role",
            "AWS::CloudFormation::StackSet",
            "AWS::Lambda::Function",
            "Custom::PublishRoleDetail",
            "AWS::KMS::Key",
            "AWS::S3::Bucket",
            "AWS::S3::BucketPolicy",
            "AWS::SQS::Queue",
            "AWS::SNS::Topic",
            "AWS::SNS::TopicPolicy",
            "AWS::CloudTrail::Trail",
            "AWS::SNS::Subscription",
            "AWS::SQS::QueuePolicy",
            # Add other resource types from P1-T1.2 as needed
        ]
        for resource_type in expected_resource_types:
            self.assertIn(resource_type, RESOURCE_ACTION_MAP, f"Resource type {resource_type} not found in RESOURCE_ACTION_MAP")

    def test_key_operation_keys_present(self):
        resource_types_to_check = [
            "AWS::IAM::Role",
            "AWS::S3::Bucket",
            "AWS::Lambda::Function",
            "AWS::CloudFormation::StackSet",
        ]
        expected_operations = ["Create", "Update", "Delete", "Tag"]
        for resource_type in resource_types_to_check:
            self.assertIn(resource_type, RESOURCE_ACTION_MAP, f"Resource type {resource_type} not found for operation key check")
            resource_data = RESOURCE_ACTION_MAP[resource_type]
            self.assertIn("operation_actions", resource_data, f"operation_actions not found for {resource_type}")
            for operation in expected_operations:
                self.assertIn(operation, resource_data["operation_actions"], f"Operation {operation} not found for {resource_type}")

    def test_accurate_action_lists(self):
        # Based on tasks/P1-T1.2-IdentifyIAMActions.md
        expected_mappings = {
            "AWS::IAM::Role": {
                "Create": ["iam:CreateRole", "iam:PutRolePolicy", "iam:AttachRolePolicy", "iam:TagRole"],
            },
            "AWS::S3::Bucket": {
                "Delete": ["s3:DeleteBucket"],
            },
            "AWS::Lambda::Function": {
                "Update": ["lambda:UpdateFunctionConfiguration", "lambda:UpdateFunctionCode", "lambda:TagResource", "lambda:UntagResource"],
            },
            "AWS::CloudFormation::StackSet": {
                "Create": ["cloudformation:CreateStackSet", "cloudformation:CreateStackInstances", "cloudformation:TagResource"],
            },
             "AWS::SQS::QueuePolicy": {
                "Create": ["sqs:AddPermission"],
            }
            # Add more specific checks as needed
        }

        for resource_type, operations in expected_mappings.items():
            self.assertIn(resource_type, RESOURCE_ACTION_MAP, f"Resource type {resource_type} not found for action list check")
            resource_data = RESOURCE_ACTION_MAP[resource_type]
            self.assertIn("operation_actions", resource_data, f"operation_actions not found for {resource_type}")
            for operation, expected_actions in operations.items():
                self.assertIn(operation, resource_data["operation_actions"], f"Operation {operation} not found for {resource_type} action list check")
                actual_actions = resource_data["operation_actions"][operation]
                # Sort lists for comparison as order might not be guaranteed or important
                self.assertEqual(sorted(actual_actions), sorted(expected_actions), f"Action list mismatch for {resource_type} operation {operation}")


if __name__ == '__main__':
    unittest.main()