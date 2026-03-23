"""Helpers for loading and updating runtime policy specifications.

The active policy catalogs that drive Sentinel's runtime Gatekeeper workflow
live in ``src/sentinel/gatekeeper/policies/policy_specs.json``.

Tests under ``tests/`` validate behavior, but runtime policy loading does not
depend on test modules.
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence

from sentinel.core.languages import Language


_CATALOG_REL_PATH = Path("src/sentinel/gatekeeper/policies/policy_specs.json")
_LANGUAGE_KEY_MAP = {
    Language.PYTHON: "PYTHON",
    Language.JAVA: "JAVA",
    Language.TYPESCRIPT: "TYPESCRIPT",
}


def project_root() -> Path:
    """Return the repository root for the current Sentinel checkout."""
    return Path(__file__).resolve().parents[3]


def catalog_path() -> Path:
    """Return the runtime policy catalog file path."""
    return project_root() / _CATALOG_REL_PATH


def _load_catalog() -> Dict[str, List[Dict[str, Any]]]:
    path = catalog_path()
    if not path.is_file():
        raise FileNotFoundError(f"Runtime policy catalog not found: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Runtime policy catalog must be a JSON object keyed by language.")
    return payload


def _save_catalog(payload: Dict[str, List[Dict[str, Any]]]) -> None:
    path = catalog_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def _language_key(language: Language) -> str:
    try:
        return _LANGUAGE_KEY_MAP[language]
    except KeyError as exc:
        raise ValueError(f"Unsupported policy language: {language!r}") from exc


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

    name = str(
        spec.get("name")
        or spec.get("name1")
        or spec.get("policy_name")
        or ""
    ).strip()
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
    """Load normalized runtime policy specs for *language* from the catalog."""
    payload = _load_catalog()
    specs = payload.get(_language_key(language), [])
    if not isinstance(specs, list):
        raise ValueError(f"Policy catalog entry for {language.name} must be a list.")
    return [normalize_policy_spec(spec) for spec in specs]


def load_policy_specs_for_languages(languages: Iterable[Language]) -> List[Dict[str, Any]]:
    """Load all normalized runtime policy specs for the given languages."""
    specs: List[Dict[str, Any]] = []
    seen = set()
    for language in languages:
        if language in seen or language not in _LANGUAGE_KEY_MAP:
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


def update_policy_specs(new_specs: Sequence[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    """Merge *new_specs* into the runtime policy catalog.

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
    payload = _load_catalog()

    for language, specs in grouped.items():
        key = _language_key(language)
        existing_raw = payload.get(key, [])
        if not isinstance(existing_raw, list):
            existing_raw = []

        existing = [normalize_policy_spec(spec) for spec in existing_raw]
        existing_keys = {_policy_identity(spec) for spec in existing}
        merged = _merge_policy_specs(existing, specs)
        merged_keys = {_policy_identity(spec) for spec in merged}
        added_keys = merged_keys - existing_keys

        if added_keys:
            payload[key] = merged
            added_by_language[language.name] = [spec for spec in merged if _policy_identity(spec) in added_keys]

    if added_by_language:
        _save_catalog(payload)

    return added_by_language