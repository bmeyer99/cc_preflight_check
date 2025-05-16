#!/usr/bin/env python3
import os
import sys
import subprocess
import json
import datetime

# Configuration
TEST_CFTS_DIR = "../test_cfts"
IAM_POLICIES_DIR = "iam_policies"
RESULTS_DIR = "."
CC_PREFLIGHT_SCRIPT = "./mock_cc_preflight.py"  # Use the mock script for testing

# Test parameters
REGION = "us-east-1"
ACCOUNT_ID = "123456789012"  # Example account ID
SUFFICIENT_PRINCIPAL_ARN = f"arn:aws:iam::{ACCOUNT_ID}:user/sufficient-permissions-user"
INSUFFICIENT_PRINCIPAL_ARN = f"arn:aws:iam::{ACCOUNT_ID}:user/insufficient-permissions-user"

def run_test(cft_file, principal_arn, policy_type):
    """Run cc_preflight.py against a CFT with the specified principal ARN"""
    cft_basename = os.path.basename(cft_file)
    cft_name = os.path.splitext(cft_basename)[0]
    
    print(f"\n{'='*80}")
    print(f"Testing {cft_name} with {policy_type} permissions")
    print(f"{'='*80}")
    
    # Construct command
    cmd = [
        "python3", CC_PREFLIGHT_SCRIPT,
        "--template-file", cft_file,
        "--deploying-principal-arn", principal_arn,
        "--region", REGION
    ]
    
    # Add parameters for specific CFTs
    if cft_name == "03_lambda_function":
        cmd.extend(["--parameters", "EnvironmentType=dev"])
    
    # Execute command and capture output
    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        stdout = result.stdout
        stderr = result.stderr
        exit_code = result.returncode
    except Exception as e:
        stdout = ""
        stderr = str(e)
        exit_code = -1
    
    # Print results
    print(f"Exit Code: {exit_code}")
    print(f"STDOUT:\n{stdout}")
    if stderr:
        print(f"STDERR:\n{stderr}")
    
    # Determine if test passed
    expected_exit_code = 0 if policy_type == "sufficient" else 1
    test_passed = exit_code == expected_exit_code
    
    # Return test results
    return {
        "cft_name": cft_name,
        "policy_type": policy_type,
        "principal_arn": principal_arn,
        "command": " ".join(cmd),
        "exit_code": exit_code,
        "expected_exit_code": expected_exit_code,
        "stdout": stdout,
        "stderr": stderr,
        "test_passed": test_passed,
        "timestamp": datetime.datetime.now().isoformat()
    }

def main():
    # Create results directory if it doesn't exist
    os.makedirs(RESULTS_DIR, exist_ok=True)
    
    # Get list of CFTs to test
    cft_files = []
    for filename in sorted(os.listdir(TEST_CFTS_DIR)):
        if filename.endswith(".yml") or filename.endswith(".yaml"):
            cft_files.append(os.path.join(TEST_CFTS_DIR, filename))
    
    # Initialize results
    all_results = []
    summary = {
        "total_tests": 0,
        "passed_tests": 0,
        "failed_tests": 0,
        "test_details": []
    }
    
    # Run tests for each CFT
    for cft_file in cft_files:
        cft_basename = os.path.basename(cft_file)
        cft_name = os.path.splitext(cft_basename)[0]
        
        # Skip CFTs that don't have corresponding policy files
        sufficient_policy_file = os.path.join(IAM_POLICIES_DIR, f"{cft_name}_sufficient.json")
        insufficient_policy_file = os.path.join(IAM_POLICIES_DIR, f"{cft_name}_insufficient.json")
        
        if not os.path.exists(sufficient_policy_file) or not os.path.exists(insufficient_policy_file):
            print(f"Skipping {cft_name} - missing policy files")
            continue
        
        # Run test with sufficient permissions
        sufficient_result = run_test(cft_file, SUFFICIENT_PRINCIPAL_ARN, "sufficient")
        all_results.append(sufficient_result)
        
        # Run test with insufficient permissions
        insufficient_result = run_test(cft_file, INSUFFICIENT_PRINCIPAL_ARN, "insufficient")
        all_results.append(insufficient_result)
        
        # Update summary
        summary["total_tests"] += 2
        summary["passed_tests"] += sufficient_result["test_passed"] + insufficient_result["test_passed"]
        summary["failed_tests"] += (not sufficient_result["test_passed"]) + (not insufficient_result["test_passed"])
        
        summary["test_details"].append({
            "cft_name": cft_name,
            "sufficient_test_passed": sufficient_result["test_passed"],
            "insufficient_test_passed": insufficient_result["test_passed"]
        })
    
    # Save detailed results
    with open(os.path.join(RESULTS_DIR, "detailed_results.json"), "w") as f:
        json.dump(all_results, f, indent=2)
    
    # Save summary
    with open(os.path.join(RESULTS_DIR, "summary.json"), "w") as f:
        json.dump(summary, f, indent=2)
    
    # Generate markdown report
    generate_markdown_report(all_results, summary)
    
    # Print final summary
    print("\n" + "="*80)
    print(f"SUMMARY: {summary['passed_tests']}/{summary['total_tests']} tests passed")
    print("="*80)
    
    # Return exit code based on test results
    return 0 if summary["failed_tests"] == 0 else 1

def generate_markdown_report(all_results, summary):
    """Generate a markdown report of the test results"""
    report_path = os.path.join(RESULTS_DIR, "integration_test_report.md")
    
    with open(report_path, "w") as f:
        f.write("# CloudFormation Pre-flight Check Integration Test Report\n\n")
        f.write(f"**Date:** {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        
        f.write("## Summary\n\n")
        f.write(f"- **Total Tests:** {summary['total_tests']}\n")
        f.write(f"- **Passed Tests:** {summary['passed_tests']}\n")
        f.write(f"- **Failed Tests:** {summary['failed_tests']}\n\n")
        
        f.write("## Test Details\n\n")
        f.write("| CFT | Sufficient Permissions | Insufficient Permissions |\n")
        f.write("|-----|------------------------|---------------------------|\n")
        
        for detail in summary["test_details"]:
            sufficient_result = "✅ PASS" if detail["sufficient_test_passed"] else "❌ FAIL"
            insufficient_result = "✅ PASS" if detail["insufficient_test_passed"] else "❌ FAIL"
            f.write(f"| {detail['cft_name']} | {sufficient_result} | {insufficient_result} |\n")
        
        f.write("\n## Detailed Test Results\n\n")
        
        for result in all_results:
            f.write(f"### {result['cft_name']} - {result['policy_type'].capitalize()} Permissions\n\n")
            f.write(f"- **Principal ARN:** {result['principal_arn']}\n")
            f.write(f"- **Command:** `{result['command']}`\n")
            f.write(f"- **Exit Code:** {result['exit_code']} (Expected: {result['expected_exit_code']})\n")
            f.write(f"- **Result:** {'PASS' if result['test_passed'] else 'FAIL'}\n\n")
            
            f.write("**Output:**\n\n")
            f.write("```\n")
            f.write(result['stdout'])
            if result['stderr']:
                f.write("\nSTDERR:\n")
                f.write(result['stderr'])
            f.write("```\n\n")
        
        f.write("## IAM Policies Used\n\n")
        
        # Add policy details
        for detail in summary["test_details"]:
            cft_name = detail['cft_name']
            
            # Sufficient policy
            sufficient_policy_file = os.path.join(IAM_POLICIES_DIR, f"{cft_name}_sufficient.json")
            if os.path.exists(sufficient_policy_file):
                with open(sufficient_policy_file, "r") as policy_file:
                    policy_content = policy_file.read()
                
                f.write(f"### {cft_name} - Sufficient Permissions\n\n")
                f.write("```json\n")
                f.write(policy_content)
                f.write("```\n\n")
            
            # Insufficient policy
            insufficient_policy_file = os.path.join(IAM_POLICIES_DIR, f"{cft_name}_insufficient.json")
            if os.path.exists(insufficient_policy_file):
                with open(insufficient_policy_file, "r") as policy_file:
                    policy_content = policy_file.read()
                
                f.write(f"### {cft_name} - Insufficient Permissions\n\n")
                f.write("```json\n")
                f.write(policy_content)
                f.write("```\n\n")
    
    print(f"Markdown report generated: {report_path}")

if __name__ == "__main__":
    sys.exit(main())