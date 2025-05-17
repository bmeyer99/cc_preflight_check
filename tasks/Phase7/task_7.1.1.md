# Task Status (DO NOT DELETE)
- **ID**: 7.1.1
- **Title**: Modularize cc_preflight.py
- **AssignedTo**: architect
- **From**: User
- **Priority**: High
- **Status**: Completed
## Details
### Requirements:
- Split the `cc_preflight.py` script into multiple, smaller, more focused Python modules.
- Ensure all original functionality is preserved after refactoring.
- Adhere to the 500 lines per file limit where feasible.
- Update imports accordingly in all affected files.
### Acceptance Criteria (AC):
- The `cc_preflight.py` script is significantly reduced in line count.
- New Python modules are created, each with a clear responsibility.
- The tool runs correctly with the refactored code, passing existing tests (if any, or behaving as before).
## Planning
- **Dependencies**: None
- **Effort**: Medium
- **Start Date**: 2025-05-17 00:07
- **End Date**: 2025-05-17 00:15
## Documentation
### Outcome/Summary:
Successfully modularized the `cc_preflight.py` script by splitting it into multiple, smaller, more focused Python modules. The original file has been reduced from over 1200 lines to just 35 lines, with all functionality preserved across the new modules.

The modularization followed the proposed plan, creating the following new modules:

The `cc_preflight.py` script will be refactored into the following new modules:

1.  **`cc_preflight_exceptions.py`**:
    *   Will contain all custom exception classes (e.g., `CCPreflightError`, `TemplateError`).
    *   Currently lines: 34-57.

2.  **`cfn_yaml_handler.py`**:
    *   Will handle YAML parsing logic, including all `cfn_*_constructor` functions and their registrations with `yaml.SafeLoader` and `yaml.CSafeLoader`.
    *   Will also include the `_load_template` function.
    *   Currently lines: 59-191, 520-570.

3.  **`aws_utils.py`**:
    *   Will group utility functions for interacting with AWS services.
    *   Includes: `get_aws_account_id`, `get_aws_profiles`, `get_current_identity`, `list_organizational_units`.
    *   Currently lines: 207-226, 1021-1113.

4.  **`condition_evaluator.py`**:
    *   Will be dedicated to the `evaluate_condition` function and its logic.
    *   Currently lines: 227-315.

5.  **`resource_processor.py`**:
    *   Will manage logic related to CloudFormation resource name resolution, ARN construction, and property-specific handling.
    *   Includes: `RESOURCE_NAME_PROPERTIES` constant, `_cached_resolve_resource_name`, `resolve_resource_name`, `_cached_construct_resource_arn`, `construct_resource_arn`, `handle_pass_role`.
    *   Currently lines: 194-205, 318-518.

6.  **`template_analyzer.py`**:
    *   This module will house the core logic for parsing the template and collecting actions.
    *   Primarily the `parse_template_and_collect_actions` function.
    *   Currently lines: 571-762.

7.  **`iam_prerequisites.py`**:
    *   Will contain the `check_prerequisites` function.
    *   Currently lines: 764-836.

8.  **`iam_simulator.py`**:
    *   Will be responsible for the `simulate_iam_permissions` function.
    *   Currently lines: 839-994.

9.  **`cli_handler.py`**:
    *   Will manage command-line argument parsing (`argparse`), user interaction (`prompt_user`), and parameter handling (`get_template_parameters`).
    *   The main `main()` function will reside here, significantly refactored to orchestrate calls to the new modules.
    *   Currently lines: 996-1018, 1115-1134, 1137-1492.

The original `cc_preflight.py` file has been substantially reduced to just 36 lines. It now serves as a simple entry point that imports the main function from `cli_handler.py`.

Each module has been designed with a clear responsibility and maintains the original functionality while improving code organization and maintainability.

Additionally, the README.md file has been updated to reflect the new modular structure, particularly in the "Extending the Tool" section which now includes information about the modular architecture and the correct file paths for extending different aspects of the tool.

The modularized code has been tested with a real CloudFormation template (`connectors_aws_cf-d33f925f6195475daf212fdc8b1919e2-1747407759.yml`) and successfully performed the pre-flight check, identifying prerequisite issues and missing IAM permissions. This confirms that the functionality has been preserved after the modularization.

### Issues/Blockers:
- None encountered.
### Files:
- `cc_preflight.py` (to be modified)
- `cc_preflight_exceptions.py` (new)
- `cfn_yaml_handler.py` (new)
- `aws_utils.py` (new)
- `condition_evaluator.py` (new)
- `resource_processor.py` (new)
- `template_analyzer.py` (new)
- `iam_prerequisites.py` (new)
- `iam_simulator.py` (new)
- `cli_handler.py` (new)
- `tasks/Phase7/task_7.1.1.md` (new)