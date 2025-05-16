#!/bin/bash

# Set up mock AWS credentials
export AWS_CONFIG_FILE="$(pwd)/mock_aws_config"
export AWS_SHARED_CREDENTIALS_FILE="$(pwd)/mock_aws_credentials"

# Create a mock STS response for get_caller_identity
mkdir -p mock_aws_responses
cat > mock_aws_responses/get_caller_identity.json << EOF
{
  "UserId": "AIDACKCEVSQ6C2EXAMPLE",
  "Account": "123456789012",
  "Arn": "arn:aws:iam::123456789012:user/test-user"
}
EOF

# Run the integration tests
echo "Running integration tests with mock AWS credentials..."
python3 run_integration_tests.py

# Check the exit code
if [ $? -eq 0 ]; then
  echo "All tests passed!"
else
  echo "Some tests failed. Check the report for details."
fi

# Clean up
unset AWS_CONFIG_FILE
unset AWS_SHARED_CREDENTIALS_FILE