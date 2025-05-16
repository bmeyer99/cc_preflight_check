# Project Plan: Robust CloudFormation Pre-flight Check Script

## Project Goal
To develop a robust Python script that performs comprehensive pre-flight checks for AWS CloudFormation templates (CFTs), with an initial focus on the Cortex XDR CFT ([`connectors_aws_cf-d33f925f6195475daf212fdc8b1919e2-1747407759.yml`](connectors_aws_cf-d33f925f6195475daf212fdc8b1919e2-1747407759.yml)). The script will aim to accurately simulate IAM permissions for the deploying principal, validate prerequisites, and significantly reduce CloudFormation deployment failures by proactively identifying issues.

## Current State
A foundational Python script exists that can parse a YAML CFT.
It attempts to map common AWS resource types to IAM actions via `RESOURCE_ACTION_MAP`.
It performs basic resolution of `!Ref` (to parameters/globals), `!Sub` (simple), and `!Join`.
It uses `iam:SimulatePrincipalPolicy` for permission checks.
It includes basic prerequisite checking (e.g., `OutpostRoleArn` existence).

Limitations include: incomplete `RESOURCE_ACTION_MAP`, limited intrinsic function handling, basic ARN prediction (often relying on wildcards), no evaluation of CFT Conditions, and no deep validation for complex resources like StackSets or custom resource internal logic.

## Phased Development Approach
We will approach this in iterative phases to manage complexity and deliver incremental improvements. Each phase represents a significant milestone.

### Phase 1: Core Enhancements - IAM Action Mapping & Basic Intrinsic Functions
**Objective Milestone:** Significantly improve the accuracy of IAM permission checks by expanding the `RESOURCE_ACTION_MAP` for all resources in the Cortex XDR CFT and enhancing basic intrinsic function resolution.

**Key Tasks:**

1.  **Exhaustive `RESOURCE_ACTION_MAP` Population for Cortex XDR CFT:**
    *   Task 1.1: Systematically review every resource type and property within the [`connectors_aws_cf-d33f925f6195475daf212fdc8b1919e2-1747407759.yml`](connectors_aws_cf-d33f925f6195475daf212fdc8b1919e2-1747407759.yml) template.
    *   Task 1.2: For each resource and its properties, consult the official AWS documentation (CloudFormation User Guide, Service Authorization Reference, service-specific API docs) to identify all required IAM actions for creation, update, deletion, and tagging. Pay special attention to actions needed for specific properties (e.g., setting an S3 bucket policy needs `s3:PutBucketPolicy` on the bucket).
    *   Task 1.3: Update `RESOURCE_ACTION_MAP` with:
        *   Accurate `generic_actions`.
        *   More precise `arn_patterns` where possible (even if still using some placeholders).
        *   Detailed `property_actions` mapping specific CFT properties to their required IAM actions.
        *   Specific tagging actions for each resource type (e.g., `iam:TagRole`, `s3:PutBucketTagging`, `lambda:TagResource`).
    *   Focus from CFT: `AWS::IAM::Role` (inline policies, managed policies, assume role docs), `AWS::S3::Bucket` (encryption, lifecycle, policy sub-resource), `AWS::KMS::Key` (key policy), `AWS::CloudTrail::Trail` (S3 bucket interactions, KMS key interactions, CWL interactions if applicable), `AWS::Lambda::Function` (`iam:PassRole`), `AWS::SQS::Queue`, `AWS::SNS::Topic`, `AWS::SNS::Subscription`.

2.  **Improved Basic Intrinsic Function Resolution (`resolve_value` function):**
    *   Task 2.1: Enhance `!Ref` to handle references to other logical resources within the same template. This might involve creating placeholder ARNs based on the logical ID and resource type for simulation purposes.
    *   Task 2.2: Improve `!Sub` to robustly handle its list form (`Fn::Sub: [String, { VarMap }]`) and nested intrinsic functions within the substitution string.
    *   Task 2.3: Ensure `!Join` correctly resolves nested functions for each element before joining.

3.  **Refined ARN Pattern Generation:**
    *   Task 3.1: For resources where CloudFormation generates names if not explicitly provided (e.g., some IAM roles, Lambda functions), research the typical naming patterns (e.g., `stackName-logicalId-randomString`) and incorporate more specific placeholders into `arn_patterns`.
    *   Task 3.2: Ensure account ID and region are correctly and consistently applied in all ARN patterns.

4.  **Unit Testing Framework:**
    *   Task 4.1: Implement unit tests for `resolve_value()` with various intrinsic function examples.
    *   Task 4.2: Implement unit tests for `RESOURCE_ACTION_MAP` lookups and action aggregation.

**Success Metrics/Deliverables for this Milestone:**
*   `RESOURCE_ACTION_MAP` covers >95% of actions for resources in the Cortex XDR CFT.
*   `resolve_value()` correctly handles all `!Ref` (to params/globals/logical IDs), `!Sub` (string & list form with param/global refs), and `!Join` examples from the Cortex XDR CFT.
*   Reduced number of "Warning: No specific IAM action mapping found..." messages.
*   More specific ARNs used in simulation (fewer broad wildcards).
*   Basic unit test suite passing.

### Phase 2: Advanced Intrinsic Functions & Conditional Logic
**Objective Milestone:** Handle more complex CFT constructs like `!GetAtt`, `!If` (and other conditions), and other less common intrinsic functions to improve the accuracy of resource property interpretation and action derivation.

**Key Tasks:**

1.  **`!GetAtt` Resolution (Predictive/Placeholder):**
    *   Task 1.1: Research common `!GetAtt` patterns for resources in the Cortex XDR CFT (e.g., `!GetAtt MyRole.Arn`, `!GetAtt MyLambda.Arn`, `!GetAtt MyS3Bucket.DomainName`).
    *   Task 1.2: Implement logic in `resolve_value()` to return a predictive placeholder for `!GetAtt` results based on the resource type and attribute. For ARNs, this would be a simulated ARN pattern. For other attributes, it might be a type-correct placeholder (e.g., "string_placeholder", "list_placeholder"). This is crucial as actual values are unknown pre-flight.

2.  **CFT Condition Evaluation (Basic Support):**
    *   Task 2.1: Allow users to optionally provide input values for CFT Condition functions (e.g., via a new CLI argument `--condition-values "IsProd=true"`).
    *   Task 2.2: Implement logic to parse the `Conditions` block of the CFT.
    *   Task 2.3: When processing resources, check if they have a `Condition` key. If so, evaluate the condition based on provided values (and intrinsic functions like `!Equals`, `!Not`, `!And`, `!Or` within the condition).
    *   Task 2.4: If a condition evaluates to false, skip collecting actions for that resource and its properties.
    *   Focus from CFT: While the Cortex XDR CFT doesn't heavily use complex conditions, this builds foundational capability.

3.  **Support for Other Intrinsic Functions:**
    *   Task 3.1: Identify other intrinsic functions used in the Cortex XDR CFT or commonly found (e.g., `!Select`, `!Split`, `!FindInMap`, `!ImportValue`).
    *   Task 3.2: Implement basic resolution logic for these in `resolve_value()`. `!ImportValue` is particularly challenging as it requires an AWS API call to check for existing exports.

4.  **Enhanced Prerequisite Checking:**
    *   Task 4.1: Expand `check_prerequisites()` to validate more than just IAM role existence. For example, if a parameter expects an S3 bucket ARN, check if the bucket exists and if the deploying principal can access it (e.g., `s3:ListBucket`).

**Success Metrics/Deliverables for this Milestone:**
*   `!GetAtt` for common attributes (especially ARNs) returns predictable patterns.
*   Script can optionally skip resources based on user-provided condition evaluations.
*   Basic support for additional intrinsic functions like `!Select`.
*   More robust prerequisite validation for different resource types.

### Phase 3: Contextual Awareness & Simulation Specificity
**Objective Milestone:** Improve the precision of the IAM simulation by incorporating more contextual information (IAM Condition Keys) and refining how resource interactions are modeled.

**Key Tasks:**

1.  **Advanced `ContextEntries` for Simulation:**
    *   Task 1.1: Systematically identify IAM Condition keys used in the inline policies and trust policies of roles created by the Cortex XDR CFT (e.g., `sts:ExternalId`, `ec2:ResourceTag/...`, `kms:ViaService`, `kms:GrantIsForAWSResource`).
    *   Task 1.2: Enhance the script to allow users to provide values for common context keys via CLI arguments (e.g., `--context-key "aws:RequestTag/Team=Blue"`).
    *   Task 1.3: Automatically derive some `ContextEntries` if possible (e.g., `sts:ExternalId` is already handled; consider others like `aws:SourceArn` if a resource triggers another).
    *   Focus from CFT: `sts:ExternalId` (already present), conditions in `Cortex-Agentless-Policy` like `ec2:Add/userId`, `ec2:ResourceTag/managed_by`, `ec2:CreateAction`, `aws:RequestTag/managed_by`, `kms:ViaService`, `kms:GrantIsForAWSResource`.

2.  **Modeling Resource-to-Resource Permissions:**
    *   Task 2.1: For scenarios where one created resource needs to grant permissions to another created resource (e.g., an SQS Queue Policy granting `sqs:SendMessage` to an SNS Topic also created in the template), the current simulation might not fully capture this if it only checks the deploying principal.
    *   Task 2.2: This is highly advanced. A potential approach is to identify such interactions and, after simulating the deploying principal's ability to create both, perform a secondary, more targeted simulation or static analysis of the generated policy if its content can be fully resolved pre-flight. (This task might be deferred or simplified).

3.  **Refined Handling of `iam:PassRole`:**
    *   Task 3.1: Ensure that for every instance where a role is passed to a service (e.g., Lambda's `Role` property, CloudTrail's `RoleArn` for CWL), the `iam:PassRole` action is checked against the correct role ARN being passed and for the correct service principal that will be assuming/using it.
    *   Focus from CFT: Execution roles for `CortexTemplateCustomLambdaFunction` and `EmptyBucketLambda`.

**Success Metrics/Deliverables for this Milestone:**
*   IAM simulations are more accurate due to relevant `ContextEntries`.
*   `iam:PassRole` checks are robust and target the correct role and service.
*   Clearer reporting on why a simulation might pass/fail due to context.

### Phase 4: Usability, Reporting, and Complex Resource Deep Dive
**Objective Milestone:** Improve user experience, provide more actionable reports, and specifically address the complexities of `AWS::CloudFormation::StackSet` and Custom Resources.

**Key Tasks:**

1.  **Enhanced Reporting and Output:**
    *   Task 1.1: Provide more detailed error messages, including suggestions for missing permissions if possible (e.g., "Action X on Resource Y denied. Consider adding Z to the deploying principal's policy.").
    *   Task 1.2: Option for different output formats (e.g., JSON, HTML report).
    *   Task 1.3: Clearly distinguish between "definitely denied" vs. "conditionally denied" (if context keys are missing) vs. "allowed with wildcards."

2.  **`AWS::CloudFormation::StackSet` Deep Dive (Cortex XDR CFT Specific):**
    *   Task 2.1: Analyze the `CortexPlatformCloudRoleStackSetMember` resource in the CFT. It uses `PermissionModel: SERVICE_MANAGED` and `AutoDeployment: Enabled: 'True'`.
    *   Task 2.2: For the deploying principal (in the management account), verify permissions like `cloudformation:CreateStackSet`, `cloudformation:DeleteStackSet`, `organizations:ListAccountsForParent`, `organizations:DescribeOrganizationUnit` (if OUs are targets).
    *   Task 2.3: Limitation Acknowledgment: Clearly document that for `SERVICE_MANAGED` StackSets, the actual cross-account resource creation permissions are handled by AWS Organizations and service-linked roles. This script cannot easily simulate those cross-account permissions directly for the deploying principal. The check will focus on the principal's ability to manage the StackSet resource itself and its OU targeting.

3.  **Custom Resource Validation (`Custom::*`):**
    *   Task 3.1: Ensure the script robustly checks permissions to create the backing `AWS::Lambda::Function` and its `AWS::IAM::Role` (execution role) for all custom resources in the CFT.
    *   Task 3.2: Documentation: Clearly state that the script does not validate the internal logic of the custom resource Lambda (e.g., the external HTTP PUT by `CortexTemplateCustomLambdaFunction`). The pre-flight check is for the deploying principal's ability to set up the custom resource framework.

4.  **Configuration File for `RESOURCE_ACTION_MAP`:**
    *   Task 4.1: Allow `RESOURCE_ACTION_MAP` to be loaded from an external YAML/JSON file, making it easier for users to extend without modifying the script's core code.

**Success Metrics/Deliverables for this Milestone:**
*   More user-friendly and actionable output.
*   Clear documentation and checks for `AWS::CloudFormation::StackSet` management permissions (with stated limitations on cross-account simulation).
*   Robust checks for setting up custom resource Lambda/roles.
*   Externalizable `RESOURCE_ACTION_MAP`.

### Phase 5: Comprehensive Testing, Documentation, and Refinement
**Objective Milestone:** Ensure the script is reliable, well-documented, and robust through thorough testing and final code cleanup.

**Key Tasks:**

1.  **Integration Testing:**
    *   Task 1.1: Create various small, targeted CFTs that test specific resource types, intrinsic functions, and IAM permission scenarios.
    *   Task 1.2: Run the script against these test CFTs with IAM principals that have known (and intentionally insufficient) permissions to verify the script's detection capabilities.
    *   Task 1.3: Test with the full Cortex XDR CFT against a principal with full admin rights (should pass all relevant checks) and a principal with limited rights.

2.  **Code Refactoring and Optimization:**
    *   Task 2.1: Review code for clarity, efficiency, and adherence to Python best practices.
    *   Task 2.2: Optimize any performance bottlenecks, especially in template parsing and action collection.

3.  **Finalize README and Inline Documentation:**
    *   Task 3.1: Update the [`README.md`](README.md) with all new features, parameters, limitations, and extension guides from all phases.
    *   Task 3.2: Ensure all functions and complex logic blocks have clear inline comments.

4.  **Error Handling and Edge Cases:**
    *   Task 4.1: Review error handling for robustness (e.g., malformed templates, invalid ARNs, AWS API errors).
    *   Task 4.2: Consider edge cases (e.g., empty resource blocks, unusual parameter types).

**Success Metrics/Deliverables for this Milestone:**
*   High unit and integration test coverage.
*   Script successfully identifies known permission issues in test scenarios.
*   Comprehensive and up-to-date [`README.md`](README.md).
*   Well-commented and maintainable codebase.
*   A stable, robust version of the script.

## Cross-Cutting Concerns

### Testing Strategy:
*   **Unit Tests:** PyTest or Python's `unittest` for individual functions (especially `resolve_value`, `RESOURCE_ACTION_MAP` interaction logic).
*   **Integration Tests:** Using actual CFT snippets and `moto` (for mocking AWS services) or live AWS accounts (with caution and cleanup) to test the end-to-end simulation process.

### Documentation:
*   **Inline Comments:** Explain complex logic, assumptions, and "why" things are done.
*   **[`README.md`](README.md):** Continuously update as the single source of truth for users and developers.

### Version Control:
*   Use Git for source code management, with meaningful commit messages and potentially feature branches for larger changes.

## Resource Considerations (High-Level)
*   **Developer Effort:** Significant investment, especially for deep IAM research and complex function handling.
*   **AWS Account for Testing:** An AWS account (preferably non-production) is needed for testing `iam:SimulatePrincipalPolicy` against real IAM principals and for validating prerequisite checks.

## Risks and Mitigation

*   **Risk: IAM Complexity:** AWS IAM is vast and nuanced. Mapping all actions perfectly is challenging.
    *   **Mitigation:** Iterative development, focus on the target CFT first, extensive use of AWS documentation, community knowledge, and clear documentation of limitations.
*   **Risk: CFT Complexity:** Advanced CFTs can be very hard to parse and interpret statically.
    *   **Mitigation:** Start with common patterns, incrementally add support for more intrinsic functions, and clearly document what is/isn't supported.
*   **Risk: Over-reliance on Wildcards in Simulation:** Wildcards can lead to false positives.
    *   **Mitigation:** Continuously strive to make ARN pattern generation more specific. Clearly explain this limitation to users.
*   **Risk: Scope Creep:** The desire for perfect simulation can lead to endless development.
    *   **Mitigation:** Stick to the phased approach. Define clear deliverables for each phase/milestone. Prioritize features based on impact for the target CFT.

## Future Considerations (Beyond This "Robust" Version)
*   Service Quota Checks: Integrate checks against AWS Service Quotas to warn if the template might exceed account limits.
*   Cost Estimation (Basic): Very basic pre-flight cost estimation based on resources (highly complex to do accurately).
*   Security Best Practice Checks: Basic checks for IAM best practices (e.g., warning against overly permissive inline policies if they can be determined).
*   Graphical User Interface (Web App): For easier use by a broader audience.
*   Integration with Linters: Leverage existing CFT linters (like `cfn-lint`) and focus this script purely on IAM pre-flight.

This project plan provides a structured path to significantly enhance the pre-flight check script. Each phase builds upon the last, moving towards a more accurate, reliable, and user-friendly tool.