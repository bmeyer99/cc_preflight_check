#!/usr/bin/env python3
"""
Profiling script for cc_preflight.py.

This script profiles the performance of the cc_preflight.py script
with a focus on large CloudFormation templates. It uses Python's cProfile
module to collect performance metrics and pstats to analyze and display
the results.

The script measures:
- Overall execution time
- Number of actions collected
- Number of resource ARNs generated
- Detailed profiling information for the top time-consuming functions
"""

import cProfile
import pstats
import io
import sys
import time
from cc_preflight import parse_template_and_collect_actions

def profile_template_parsing(template_path, parameters=None, account_id="123456789012", region="us-east-1"):
    """
    Profile the parsing of a CloudFormation template.
    
    This function:
    1. Sets up profiling using cProfile
    2. Calls parse_template_and_collect_actions with the provided template
    3. Measures execution time
    4. Collects statistics on actions and resource ARNs
    5. Prints detailed profiling information
    
    Args:
        template_path: Path to the CloudFormation template
        parameters: Dictionary of parameter values (default: empty dict)
        account_id: AWS account ID (default: 123456789012)
        region: AWS region (default: us-east-1)
        
    Returns:
        Tuple containing:
        - Execution time in seconds
        - Number of actions collected
        - Number of resource ARNs generated
    """
    if parameters is None:
        parameters = {}
    
    print(f"Profiling template: {template_path}")
    
    # Time the execution
    start_time = time.time()
    
    # Create a profiler
    pr = cProfile.Profile()
    pr.enable()
    
    # Run the function to profile
    actions, resource_arns, prerequisite_checks = parse_template_and_collect_actions(
        template_path, parameters, account_id, region
    )
    
    # Disable the profiler
    pr.disable()
    
    # Print execution time
    execution_time = time.time() - start_time
    print(f"Execution time: {execution_time:.4f} seconds")
    print(f"Actions collected: {len(actions)}")
    print(f"Resource ARNs: {len(resource_arns)}")
    
    # Print profiling stats
    s = io.StringIO()
    ps = pstats.Stats(pr, stream=s).sort_stats('cumulative')
    ps.print_stats(20)  # Print top 20 functions by cumulative time
    print(s.getvalue())
    
    return execution_time, len(actions), len(resource_arns)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python profile_cc_preflight.py <template_path>")
        sys.exit(1)
    
    template_path = sys.argv[1]
    profile_template_parsing(template_path)
    # The script can be extended to accept additional parameters like:
    # - CloudFormation parameters
    # - Account ID
    # - Region
    # - Condition values