"""Helpers for loading and updating test-backed policy specifications.

The policy catalogs that drive Sentinel's runtime test workflow live in the
language-specific policy test modules under ``tests/``. This module reads those
``POLICY_SPECS`` literals without importing the test modules and can update them
when the end-to-end LLM flow suggests new rules.
"""

from __future__ import annotations

import ast
from collections import defaultdict
from pathlib import Path
from pprint import pformat
from typing import Any, Dict, Iterable, List, Optional, Sequence

from sentinel.core.languages import Language


_POLICY_VAR_NAME = "POLICY_SPECS"
_LANGUAGE_FILE_MAP = {
    Language.PYTHON: Path("tests/policies_python/test_policy_python.py"),
    Language.JAVA: Path("tests/policies_java/test_policy_java.py"),
    Language.TYPESCRIPT: Path("tests/policies_ts/test_policy_ts.py"),
}


def project_root() -> Path:
    """Return the repository root for the current Sentinel checkout."""
    return Path(__file__).resolve().parents[3]


def policy_test_path(language: Language) -> Path:
    """Return the policy test file path for *language*."""
    try:
        return project_root() / _LANGUAGE_FILE_MAP[language]
    except KeyError as exc:
        raise ValueError(f"Unsupported policy language: {language!r}") from exc


def policy_test_paths() -> Dict[Language, Path]:
    """Return a copy of the language-to-policy-file mapping."""
    return {language: project_root() / rel_path for language, rel_path in _LANGUAGE_FILE_MAP.items()}


def _extract_policy_specs(content: str) -> List[Dict[str, Any]]:
    tree = ast.parse(content)
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id == _POLICY_VAR_NAME:
                specs = ast.literal_eval(node.value)
                return [normalize_policy_spec(spec) for spec in specs]
    return []


def _find_policy_assignment_node(content: str) -> Optional[ast.Assign]:
    tree = ast.parse(content)
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id == _POLICY_VAR_NAME:
                return node
    return None


def normalize_language(value: Any) -> Optional[Language]:
    """Normalize a string or enum value into a ``Language``."""
    if isinstance(value, Language):
        return value
    if not isinstance(value, str):
        return None
    key = value.strip().upper()
    try:
        return Language[key]
    except KeyError:
        return None


def normalize_policy_spec(spec: Dict[str, Any]) -> Dict[str, Any]:
    """Return a normalized policy spec dictionary."""
    language = normalize_language(spec.get("language"))
    if language is None:
        raise ValueError(f"Policy spec has unsupported language: {spec!r}")

    name = str(spec.get("name", "")).strip()
    if not name:
        raise ValueError(f"Policy spec is missing a name: {spec!r}")

    patterns = spec.get("patterns") or []
    if isinstance(patterns, str):
        patterns = [patterns]

    normalized = {
        "name": name,
        "language": language.name,
        "match_mode": str(spec.get("match_mode", "contains")).strip() or "contains",
        "patterns": [str(pattern).strip() for pattern in patterns if str(pattern).strip()],
        "description": str(spec.get("description", "")).strip(),
    }
    return normalized


def load_policy_specs(language: Language) -> List[Dict[str, Any]]:
    """Load normalized policy specs for *language* from the tests folder."""
    path = policy_test_path(language)
    return _extract_policy_specs(path.read_text(encoding="utf-8"))


def load_policy_specs_for_languages(languages: Iterable[Language]) -> List[Dict[str, Any]]:
    """Load all normalized policy specs for the given languages."""
    specs: List[Dict[str, Any]] = []
    seen = set()
    for language in languages:
        if language in seen or language not in _LANGUAGE_FILE_MAP:
            continue
        seen.add(language)
        specs.extend(load_policy_specs(language))
    return specs


def _policy_identity(spec: Dict[str, Any]) -> tuple:
    patterns = tuple(spec.get("patterns", []))
    return spec.get("name"), spec.get("language"), spec.get("match_mode"), patterns


def _merge_policy_specs(existing: Sequence[Dict[str, Any]], new_specs: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    merged: List[Dict[str, Any]] = [normalize_policy_spec(spec) for spec in existing]
    existing_by_name = {spec["name"]: spec for spec in merged}

    for raw_spec in new_specs:
        spec = normalize_policy_spec(raw_spec)
        current = existing_by_name.get(spec["name"])
        if current is None:
            merged.append(spec)
            existing_by_name[spec["name"]] = spec
            continue

        current_patterns = list(current.get("patterns", []))
        for pattern in spec.get("patterns", []):
            if pattern not in current_patterns:
                current_patterns.append(pattern)
        current["patterns"] = current_patterns

        if spec.get("description") and not current.get("description"):
            current["description"] = spec["description"]
        if spec.get("match_mode") and current.get("match_mode") == "contains":
            current["match_mode"] = spec["match_mode"]

    return merged


def _replace_policy_block(content: str, specs: Sequence[Dict[str, Any]]) -> str:
    assignment = _find_policy_assignment_node(content)
    if assignment is None:
        raise ValueError(f"{_POLICY_VAR_NAME} assignment not found in policy test file.")

    lines = content.splitlines()
    start = assignment.lineno - 1
    end = assignment.end_lineno
    replacement = f"{_POLICY_VAR_NAME} = {pformat(list(specs), sort_dicts=False, width=100)}"
    new_lines = lines[:start] + replacement.splitlines() + lines[end:]
    return "\n".join(new_lines) + "\n"


def update_policy_specs(new_specs: Sequence[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    """Merge *new_specs* into the tests-backed policy catalogs.

    Returns a mapping of language name to the specs that were newly added.
    """
    grouped: Dict[Language, List[Dict[str, Any]]] = defaultdict(list)
    for spec in new_specs:
        normalized = normalize_policy_spec(spec)
        language = normalize_language(normalized["language"])
        if language is None:
            continue
        grouped[language].append(normalized)

    added_by_language: Dict[str, List[Dict[str, Any]]] = {}
    for language, specs in grouped.items():
        path = policy_test_path(language)
        existing = load_policy_specs(language)
        existing_keys = {_policy_identity(spec) for spec in existing}
        merged = _merge_policy_specs(existing, specs)
        merged_keys = {_policy_identity(spec) for spec in merged}
        added_keys = merged_keys - existing_keys

        if added_keys:
            updated_content = _replace_policy_block(path.read_text(encoding="utf-8"), merged)
            path.write_text(updated_content, encoding="utf-8")
            added_by_language[language.name] = [spec for spec in merged if _policy_identity(spec) in added_keys]

    return added_by_language