"""Update tests-backed Sentinel policy catalogs from LLM suggestions."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List


SRC_ROOT = Path(__file__).resolve().parents[2]
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from sentinel.gatekeeper.test_policy_source import update_policy_specs


LLM_JSON_HEADER = "--- LLM Policy Suggestions JSON ---"
LLM_JSON_FOOTER = "--- End LLM Policy Suggestions JSON ---"


def _strip_code_fence(text: str) -> str:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```(?:json)?", "", stripped).strip()
        if stripped.endswith("```"):
            stripped = stripped[:-3].strip()
    return stripped


def extract_llm_policy_specs(report_text: str) -> List[Dict[str, Any]]:
    """Parse the JSON policy suggestion block from a report."""
    if LLM_JSON_HEADER not in report_text:
        return []

    section = report_text.split(LLM_JSON_HEADER, 1)[1]
    if LLM_JSON_FOOTER in section:
        section = section.split(LLM_JSON_FOOTER, 1)[0]

    payload = _strip_code_fence(section)
    if not payload:
        return []

    data = json.loads(payload)
    if isinstance(data, dict):
        data = [data]
    if not isinstance(data, list):
        raise ValueError("LLM policy suggestion block must contain a JSON list.")
    return [spec for spec in data if isinstance(spec, dict)]


def apply_policy_updates(specs: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    """Merge *specs* into the tests-backed policy catalogs."""
    return update_policy_specs(specs)


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Merge LLM policy suggestions into tests-backed POLICY_SPECS catalogs.")
    parser.add_argument("--report", required=True, help="Path to a Sentinel end-to-end report file.")
    args = parser.parse_args(argv)

    report_path = Path(args.report)
    if not report_path.is_file():
        print(f"[AutoGrow] Report not found: {report_path}")
        return 1

    report_text = report_path.read_text(encoding="utf-8")
    specs = extract_llm_policy_specs(report_text)
    if not specs:
        print("[AutoGrow] No LLM policy suggestions found in report.")
        return 0

    added = apply_policy_updates(specs)
    if not added:
        print("[AutoGrow] No new policy specs were added.")
        return 0

    for language, entries in added.items():
        print(f"[AutoGrow] Added {len(entries)} policy spec(s) for {language}.")
        for entry in entries:
            print(f"[AutoGrow]   - {entry['name']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())