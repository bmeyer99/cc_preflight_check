#!/usr/bin/env python3
"""
PDF Report Generator.

This module provides functionality for generating PDF reports from CloudFormation
pre-flight check results. It uses WeasyPrint to convert HTML/CSS to PDF, creating
professional reports with executive summaries, detailed findings, and IAM policy
suggestions for any identified shortcomings.
"""

import os
import json
import datetime
from typing import Dict, List, Any, Optional, Tuple
import tempfile

try:
    from weasyprint import HTML, CSS
    from weasyprint.text.fonts import FontConfiguration
except ImportError:
    print("WeasyPrint is required for PDF report generation.")
    print("Install it with: pip install weasyprint")
    print("For more information, visit: https://doc.courtbouillon.org/weasyprint/stable/first_steps.html")
    raise


def generate_pdf_report(
    template_file: str,
    principal_arn: str,
    region: str,
    actions: List[str],
    resource_arns: List[str],
    prereq_checks: List[Dict[str, Any]],
    prereqs_ok: bool,
    permissions_ok: bool,
    failed_simulations: List[Dict[str, Any]],
    output_file: str = None
) -> str:
    """
    Generate a PDF report from CloudFormation pre-flight check results.
    
    Args:
        template_file: Path to the CloudFormation template
        principal_arn: ARN of the principal deploying the template
        region: AWS region for deployment
        actions: List of IAM actions required
        resource_arns: List of resource ARNs
        prereq_checks: List of prerequisite checks performed
        prereqs_ok: Boolean indicating if all prerequisite checks passed
        permissions_ok: Boolean indicating if all permissions checks passed
        failed_simulations: List of failed simulation results
        output_file: Path to save the PDF report (optional)
        
    Returns:
        Path to the generated PDF file
    """
    # Create reports directory if it doesn't exist
    reports_dir = "reports"
    if not os.path.exists(reports_dir):
        os.makedirs(reports_dir)
    
    # If no output file specified, create one based on the template name in reports directory
    if not output_file:
        template_name = os.path.basename(template_file).split('.')[0]
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = os.path.join(reports_dir, f"cc_preflight_report_{template_name}_{timestamp}.pdf")
    # If output_file is just a filename (not a path), put it in the reports directory
    elif not os.path.dirname(output_file):
        output_file = os.path.join(reports_dir, output_file)
    
    # Generate HTML content
    html_content = _generate_html_content(
        template_file, principal_arn, region, actions, resource_arns,
        prereq_checks, prereqs_ok, permissions_ok, failed_simulations
    )
    
    # Generate CSS styling
    css_content = _generate_css_content()
    
    # Create temporary files for HTML and CSS
    with tempfile.NamedTemporaryFile(suffix='.html', delete=False) as html_file, \
         tempfile.NamedTemporaryFile(suffix='.css', delete=False) as css_file:
        
        html_file.write(html_content.encode('utf-8'))
        css_file.write(css_content.encode('utf-8'))
        
        html_path = html_file.name
        css_path = css_file.name
    
    try:
        # Configure fonts
        font_config = FontConfiguration()
        
        # Generate PDF
        html = HTML(filename=html_path)
        css = CSS(filename=css_path, font_config=font_config)
        
        # Render and write PDF
        html.write_pdf(output_file, stylesheets=[css], font_config=font_config)
        
        print(f"PDF report generated: {output_file}")
        return output_file
    
    finally:
        # Clean up temporary files
        try:
            os.unlink(html_path)
            os.unlink(css_path)
        except Exception as e:
            print(f"Warning: Could not remove temporary files: {e}")


def _generate_html_content(
    template_file: str,
    principal_arn: str,
    region: str,
    actions: List[str],
    resource_arns: List[str],
    prereq_checks: List[Dict[str, Any]],
    prereqs_ok: bool,
    permissions_ok: bool,
    failed_simulations: List[Dict[str, Any]]
) -> str:
    """
    Generate HTML content for the PDF report.
    
    Args:
        template_file: Path to the CloudFormation template
        principal_arn: ARN of the principal deploying the template
        region: AWS region for deployment
        actions: List of IAM actions required
        resource_arns: List of resource ARNs
        prereq_checks: List of prerequisite checks performed
        prereqs_ok: Boolean indicating if all prerequisite checks passed
        permissions_ok: Boolean indicating if all permissions checks passed
        failed_simulations: List of failed simulation results
        
    Returns:
        HTML content as a string
    """
    # Get current date and time
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Determine overall status
    overall_status = "PASS" if prereqs_ok and permissions_ok else "FAIL"
    status_color = "green" if overall_status == "PASS" else "red"
    
    # Count total actions and resources
    total_actions = len(actions)
    total_resources = len(resource_arns)
    
    # Count failed actions
    failed_actions = len(failed_simulations)
    
    # Group failed actions by resource for policy generation
    resource_to_actions = {}
    for result in failed_simulations:
        action = result.get('EvalActionName', '')
        resource = result.get('EvalResourceName', '*')
        
        if resource not in resource_to_actions:
            resource_to_actions[resource] = []
        resource_to_actions[resource].append(action)
    
    # Generate policy document for missing permissions
    policy_doc = {
        "Version": "2012-10-17",
        "Statement": []
    }
    
    for resource, actions_list in resource_to_actions.items():
        policy_doc["Statement"].append({
            "Effect": "Allow",
            "Action": sorted(actions_list),
            "Resource": resource
        })
    
    # Format policy as JSON string with indentation
    policy_json = json.dumps(policy_doc, indent=2)
    
    # Create HTML content
    html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>CloudFormation Pre-flight Check Report</title>
</head>
<body>
    <!-- Cover Page -->
    <div class="cover-page">
        <h1>CloudFormation Pre-flight Check Report</h1>
        <p class="date">Generated on: {now}</p>
        <div class="status-badge status-{status_color}">
            Overall Status: {overall_status}
        </div>
        <div class="cover-details">
            <p><strong>Template:</strong> {os.path.basename(template_file)}</p>
            <p><strong>Principal:</strong> {principal_arn}</p>
            <p><strong>Region:</strong> {region}</p>
        </div>
    </div>
    
    <!-- Table of Contents -->
    <div class="page-break"></div>
    <div class="toc-page">
        <h2>Table of Contents</h2>
        <ul class="toc">
            <li><a href="#executive-summary">1. Executive Summary</a></li>
            <li><a href="#detailed-findings">2. Detailed Findings</a>
                <ul>
                    <li><a href="#prerequisite-checks">2.1 Prerequisite Checks</a></li>
                    <li><a href="#permission-checks">2.2 Permission Checks</a></li>
                </ul>
            </li>
            <li><a href="#remediation">3. Remediation</a></li>
        </ul>
    </div>
    
    <!-- Executive Summary -->
    <div class="page-break"></div>
    <div class="content-page">
        <h2 id="executive-summary">1. Executive Summary</h2>
        <div class="summary-box">
            <p>This report presents the results of pre-flight checks for CloudFormation template deployment.</p>
            <p>The analysis evaluated a total of <strong>{total_actions}</strong> IAM actions across <strong>{total_resources}</strong> resources.</p>
            
            <div class="summary-stats">
                <div class="stat-item">
                    <div class="stat-label">Prerequisite Checks</div>
                    <div class="stat-value status-{('green' if prereqs_ok else 'red')}">{('PASS' if prereqs_ok else 'FAIL')}</div>
                </div>
                <div class="stat-item">
                    <div class="stat-label">Permission Checks</div>
                    <div class="stat-value status-{('green' if permissions_ok else 'red')}">{('PASS' if permissions_ok else 'FAIL')}</div>
                </div>
                <div class="stat-item">
                    <div class="stat-label">Failed Actions</div>
                    <div class="stat-value">{failed_actions}</div>
                </div>
            </div>
            
            <div class="summary-conclusion">
                <p><strong>Conclusion:</strong> {
                    "All checks passed. The principal has sufficient permissions to deploy the CloudFormation template." 
                    if overall_status == "PASS" else 
                    "Some checks failed. The principal lacks necessary permissions to deploy the CloudFormation template. See detailed findings for more information."
                }</p>
            </div>
        </div>
        
        <!-- Detailed Findings -->
        <h2 id="detailed-findings">2. Detailed Findings</h2>
        
        <!-- Prerequisite Checks -->
        <h3 id="prerequisite-checks">2.1 Prerequisite Checks</h3>
        <div class="findings-section">
            <p>Prerequisite checks verify that required resources exist before template deployment.</p>
            <div class="status-indicator status-{('green' if prereqs_ok else 'red')}">
                Status: {('PASS' if prereqs_ok else 'FAIL')}
            </div>
            
            <table class="findings-table">
                <thead>
                    <tr>
                        <th>Type</th>
                        <th>Resource ARN</th>
                        <th>Status</th>
                    </tr>
                </thead>
                <tbody>
"""
    
    # Add prerequisite check results
    if prereq_checks:
        for check in prereq_checks:
            check_type = check.get('type', 'Unknown')
            check_arn = check.get('arn', 'Unknown')
            check_description = check.get('description', check_type)
            
            # For simplicity, we're assuming all checks passed if prereqs_ok is True
            # In a real implementation, you'd want to track individual check results
            check_status = "PASS" if prereqs_ok else "FAIL"
            status_class = "status-green" if check_status == "PASS" else "status-red"
            
            html += f"""
                    <tr>
                        <td>{check_description}</td>
                        <td>{check_arn}</td>
                        <td class="{status_class}">{check_status}</td>
                    </tr>
"""
    else:
        html += f"""
                    <tr>
                        <td colspan="3">No prerequisite checks were performed.</td>
                    </tr>
"""
    
    html += """
                </tbody>
            </table>
        </div>
        
        <!-- Permission Checks -->
        <h3 id="permission-checks">2.2 Permission Checks</h3>
        <div class="findings-section">
            <p>Permission checks verify that the principal has the necessary IAM permissions to deploy the template.</p>
            <div class="status-indicator status-{0}">
                Status: {1}
            </div>
            
            <table class="findings-table">
                <thead>
                    <tr>
                        <th>Action</th>
                        <th>Resource</th>
                        <th>Status</th>
                        <th>Details</th>
                    </tr>
                </thead>
                <tbody>
""".format('green' if permissions_ok else 'red', 'PASS' if permissions_ok else 'FAIL')
    
    # Add failed permission check results
    if failed_simulations:
        for result in failed_simulations:
            action = result.get('EvalActionName', 'Unknown')
            resource = result.get('EvalResourceName', '*')
            decision = result.get('EvalDecision', 'Unknown')
            
            # Check for specific denial reasons
            denial_reasons = []
            if result.get('OrganizationsDecisionDetail', {}).get('AllowedByOrganizations') == False:
                denial_reasons.append("Denied by Organizations SCP")
            if result.get('PermissionsBoundaryDecisionDetail', {}).get('AllowedByPermissionsBoundary') == False:
                denial_reasons.append("Denied by Permissions Boundary")
            
            details = ", ".join(denial_reasons) if denial_reasons else decision
            
            html += f"""
                    <tr>
                        <td>{action}</td>
                        <td>{resource}</td>
                        <td class="status-red">FAIL</td>
                        <td>{details}</td>
                    </tr>
"""
    elif not permissions_ok:
        html += f"""
                    <tr>
                        <td colspan="4">Permission check failed, but no specific failed simulations were recorded.</td>
                    </tr>
"""
    else:
        html += f"""
                    <tr>
                        <td colspan="4">All permission checks passed.</td>
                    </tr>
"""
    
    html += """
                </tbody>
            </table>
        </div>
        
        <!-- Remediation -->
        <div class="page-break"></div>
        <h2 id="remediation">3. Remediation</h2>
        <div class="remediation-section">
"""
    
    if overall_status == "PASS":
        html += """
            <p>No remediation is required. All checks passed successfully.</p>
"""
    else:
        html += """
            <p>The following remediation steps are recommended to address the identified issues:</p>
"""
        
        if not prereqs_ok:
            html += """
            <h3>Prerequisite Resources</h3>
            <p>Ensure that all prerequisite resources exist before deploying the CloudFormation template:</p>
            <ul>
"""
            
            for check in prereq_checks:
                check_type = check.get('type', 'Unknown')
                check_arn = check.get('arn', 'Unknown')
                check_description = check.get('description', check_type)
                
                html += f"""
                <li>Create or verify the existence of {check_description}: {check_arn}</li>
"""
            
            html += """
            </ul>
"""
        
        if not permissions_ok:
            html += """
            <h3>IAM Permissions</h3>
            <p>Attach the following IAM policy to the principal to grant the missing permissions:</p>
            <pre class="policy-json">
"""
            
            html += policy_json.replace("<", "&lt;").replace(">", "&gt;")
            
            html += """
            </pre>
            <p>This policy grants only the specific permissions that were identified as missing during the pre-flight check.</p>
"""
    
    html += """
        </div>
    </div>
</body>
</html>
"""
    
    return html


def _generate_css_content() -> str:
    """
    Generate CSS styling for the PDF report.
    
    Returns:
        CSS content as a string
    """
    return """
@page {
    margin: 1cm;
    @top-center {
        content: "CloudFormation Pre-flight Check Report";
        font-size: 9pt;
        color: #666;
    }
    @bottom-center {
        content: "Page " counter(page) " of " counter(pages);
        font-size: 9pt;
        color: #666;
    }
}

body {
    font-family: Arial, sans-serif;
    font-size: 11pt;
    line-height: 1.5;
    color: #333;
}

.page-break {
    page-break-after: always;
}

/* Cover Page */
.cover-page {
    height: 100vh;
    display: flex;
    flex-direction: column;
    justify-content: center;
    align-items: center;
    text-align: center;
}

.cover-page h1 {
    font-size: 24pt;
    color: #0066cc;
    margin-bottom: 1cm;
}

.date {
    font-size: 12pt;
    margin-bottom: 2cm;
}

.status-badge {
    font-size: 16pt;
    font-weight: bold;
    padding: 10px 20px;
    border-radius: 5px;
    margin-bottom: 2cm;
}

.cover-details {
    text-align: left;
    width: 80%;
}

.cover-details p {
    margin: 5px 0;
}

/* Table of Contents */
.toc-page {
    padding: 2cm 1cm;
}

.toc {
    list-style-type: none;
    padding-left: 0;
}

.toc ul {
    list-style-type: none;
    padding-left: 2cm;
}

.toc a {
    text-decoration: none;
    color: #0066cc;
}

/* Content Pages */
.content-page {
    padding: 1cm 0;
}

h2 {
    color: #0066cc;
    border-bottom: 1px solid #0066cc;
    padding-bottom: 5px;
    margin-top: 1cm;
}

h3 {
    color: #0066cc;
    margin-top: 0.8cm;
}

/* Summary Box */
.summary-box {
    background-color: #f5f5f5;
    border: 1px solid #ddd;
    border-radius: 5px;
    padding: 15px;
    margin: 15px 0;
}

.summary-stats {
    display: flex;
    justify-content: space-around;
    margin: 20px 0;
}

.stat-item {
    text-align: center;
    padding: 10px;
}

.stat-label {
    font-weight: bold;
    margin-bottom: 5px;
}

.stat-value {
    font-size: 16pt;
    font-weight: bold;
}

.summary-conclusion {
    margin-top: 20px;
    font-style: italic;
}

/* Findings Section */
.findings-section {
    margin-bottom: 1cm;
}

.status-indicator {
    display: inline-block;
    padding: 5px 10px;
    border-radius: 3px;
    font-weight: bold;
    margin: 10px 0;
}

.findings-table {
    width: 100%;
    border-collapse: collapse;
    margin: 15px 0;
}

.findings-table th, .findings-table td {
    border: 1px solid #ddd;
    padding: 8px;
    text-align: left;
}

.findings-table th {
    background-color: #f2f2f2;
    font-weight: bold;
}

.findings-table tr:nth-child(even) {
    background-color: #f9f9f9;
}

/* Remediation Section */
.remediation-section {
    margin-bottom: 1cm;
}

.policy-json {
    background-color: #f5f5f5;
    border: 1px solid #ddd;
    border-radius: 3px;
    padding: 10px;
    font-family: monospace;
    white-space: pre-wrap;
    overflow-x: auto;
}

/* Status Colors */
.status-green {
    color: #2e8b57;
    background-color: #f0fff0;
}

.status-red {
    color: #b22222;
    background-color: #fff0f0;
}
"""


def update_task_status(task_file: str, status: str = "In Progress") -> None:
    """
    Update the status of the task in the task file.
    
    Args:
        task_file: Path to the task file
        status: New status to set
    """
    if not os.path.exists(task_file):
        return
    
    try:
        with open(task_file, 'r') as f:
            content = f.read()
        
        # Update status
        content = content.replace("- **Status**: Assigned", f"- **Status**: {status}")
        
        with open(task_file, 'w') as f:
            f.write(content)
    except Exception as e:
        print(f"Warning: Could not update task status: {e}")