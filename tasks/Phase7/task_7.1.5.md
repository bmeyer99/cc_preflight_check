# Task Status (DO NOT DELETE)
- **ID**: 7.1.5
- **Title**: Graceful Fallback for WeasyPrint in Report Generator
- **AssignedTo**: Archer (Architect Mode)
- **From**: User Request
- **Priority**: High
- **Status**: Completed
## Details
### Requirements:
- Modify [`report_generator.py`](report_generator.py) to handle `ImportError` for WeasyPrint.
- If WeasyPrint is not installed, the script should not crash.
- If WeasyPrint is not installed, the script should output the report content as an HTML file instead of a PDF.
- A message should be printed to the console indicating that HTML is generated due to WeasyPrint's absence.
- The IAM policy JSON generation should still function as expected.
### Acceptance Criteria (AC):
- When WeasyPrint is installed, PDF reports are generated as before.
- When WeasyPrint is not installed:
    - The script runs to completion without raising an `ImportError` related to WeasyPrint.
    - An HTML file containing the report is saved. The filename should correspond to the intended PDF filename but with an `.html` extension.
    - A console message clearly states that WeasyPrint was not found and an HTML report was generated, including the path to the HTML file.
    - The [`generate_pdf_report`](report_generator.py:122) function returns the path to the HTML file (instead of PDF) and the path to the IAM policy JSON (if applicable).
    - IAM policy JSON is generated correctly if conditions are met.
## Planning
- **Dependencies**: None
- **Effort**: Short
## Documentation
### Outcome/Summary:
Modified `report_generator.py` to gracefully handle the case when WeasyPrint is not installed. The changes include:

1. Added a global flag `WEASYPRINT_AVAILABLE` to track if WeasyPrint is available
2. Removed the `raise` statement from the `ImportError` exception handler
3. Updated the `generate_pdf_report` function to:
   - Check if WeasyPrint is available
   - Generate a PDF if it's available
   - Fall back to HTML output if WeasyPrint is not available or if PDF generation fails
   - Return the path to the generated report (either PDF or HTML)
4. Updated the function's docstring to reflect that it can return an HTML file path
5. Ensured temporary files are properly cleaned up

The implementation now satisfies all acceptance criteria, allowing the system to continue functioning even when WeasyPrint is not installed, while still providing useful output in the form of an HTML report.
### Issues/Blockers:
- None
### Files:
- [`report_generator.py`](report_generator.py)