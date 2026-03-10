"""
Sentinel AutoGrow Script

This script parses the latest Sentinel analysis report and ensures that any new violation or LLM-suggested policy is covered by a test in the relevant test_policy file. If not, it appends a template test for future implementation.
"""
import os
import re
from pathlib import Path

# Paths
REPORT_PATH = Path('tests/reports/analyze_demo_project_src_2026-03-09.txt')
POLICY_TEST_PATHS = {
    'JAVA': Path('tests/policies_java/test_policy_java.py'),
    'TYPESCRIPT': Path('tests/policies_ts/test_policy_ts.py'),
    'PYTHON': Path('tests/policies_python/test_policy_python.py'),
}

# Violation regex patterns for extraction
VIOLATION_PATTERNS = [
    re.compile(r"\[!\] (.+)")
]

# LLM suggestion section header
LLM_HEADER = '--- LLM/AI Policy Suggestions & Explanations ---'


def extract_violations(report_text):
    """Extract unique violation messages from the report."""
    violations = set()
    for pattern in VIOLATION_PATTERNS:
        violations.update(pattern.findall(report_text))
    return violations


def extract_llm_suggestions(report_text):
    """Extract LLM-suggested rules from the report."""
    if LLM_HEADER not in report_text:
        return []
    llm_section = report_text.split(LLM_HEADER, 1)[1]
    suggestions = re.findall(r"\*\*Rule\*\*: (.+)", llm_section)
    return suggestions


def test_exists(test_path, violation):
    """Check if a violation or rule is already covered in the test file."""
    with open(test_path, encoding='utf-8') as f:
        content = f.read().lower()
    return violation.lower() in content


def append_test(test_path, violation):
    """Append a template test for the new violation/rule."""
    test_name = re.sub(r'[^a-zA-Z0-9]', '_', violation)[:40]
    test_code = f"""
    def test_autogen_{test_name}(self):
            '''Auto-generated test for: {violation}'''
        # TODO: Implement test logic for this violation/rule
        self.fail('Auto-generated test: implement logic for: {violation}')
"""
    with open(test_path, 'a', encoding='utf-8') as f:
        f.write(test_code)
    print(f"[AutoGrow] Appended test for: {violation}")


def main():
    report_text = REPORT_PATH.read_text(encoding='utf-8')
    violations = extract_violations(report_text)
    llm_suggestions = extract_llm_suggestions(report_text)

    # For demo, assign all to JAVA/TS based on keywords
    for violation in violations.union(llm_suggestions):
        if 'java' in violation.lower():
            test_path = POLICY_TEST_PATHS['JAVA']
        elif 'ts' in violation.lower() or 'typescript' in violation.lower() or 'console.log' in violation.lower():
            test_path = POLICY_TEST_PATHS['TYPESCRIPT']
        elif 'python' in violation.lower():
            test_path = POLICY_TEST_PATHS['PYTHON']
        else:
            # Default to JAVA for demo
            test_path = POLICY_TEST_PATHS['JAVA']
        if not test_exists(test_path, violation):
            append_test(test_path, violation)
        else:
            print(f"[AutoGrow] Already covered: {violation}")

if __name__ == '__main__':
    main()
