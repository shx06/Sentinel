"""
Sentinel CLI entry point.

Orchestrates all 5 pillars — Historian, Guardian, Fuzzer, Sandbox, and
Gatekeeper — and prints a structured analysis report for a target repository.

Usage::

    python main.py analyze /path/to/repo
    python main.py analyze /path/to/repo --sandbox
"""

import argparse
import io
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # dotenv is optional, but recommended for .env support
import importlib.util
import inspect
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
from contextlib import redirect_stdout
from datetime import date
from typing import Any, Dict, List, Optional, Tuple

from sentinel.core.guardian import ArchitecturalGuardian
from sentinel.core.languages import Language
from sentinel.core.rules import FunctionComplexityRule, NoCircularDependenciesRule
from sentinel.fuzzer import AdversarialFuzzer, FuzzReport
from sentinel.gatekeeper import Gatekeeper, Verdict
from sentinel.gatekeeper.policy import PolicyConfig
from sentinel.gatekeeper.test_policy_autogrow import apply_policy_updates
from sentinel.gatekeeper.test_policy_source import load_policy_specs_for_languages
from sentinel.historian import ContextualHistorian

# Smoke-test script run inside the Docker sandbox.
_SANDBOX_SMOKE_TEST = "print('Sentinel sandbox check passed')"


# ---------------------------------------------------------------------------
# Pillar helpers
# ---------------------------------------------------------------------------


def _run_historian(repo_path: str) -> Optional[Any]:
    """Run the Contextual Historian pillar and return its stats."""
    print("\n[1/5] Historian: Learning from repository history...")
    import traceback
    try:
        historian = ContextualHistorian(repo_path)
        stats = historian.learn_repository(max_commits=100)
        print(f"  Commits processed: {stats.get('commits_processed', 0)}")
        return stats
    except Exception as exc:  # noqa: BLE001
        print(f"  Warning: Historian encountered an error: {exc}")
        traceback.print_exc()
        return None


def _run_guardian(repo_path: str, step_label: str = "[2/5]") -> Tuple[Dict, List[str]]:
    """Run the Architectural Guardian pillar.

    Returns:
        Tuple of (graph dict, violations list).
    """
    print(f"\n{step_label} Guardian: Scanning codebase for rule violations...")
    guardian = ArchitecturalGuardian()
    graph = guardian.analyze_structure(repo_path)
    rules = [NoCircularDependenciesRule(), FunctionComplexityRule()]
    violations = guardian.check_rules(rules)

    print(f"  Files analyzed: {len(graph)}")
    if violations:
        print(f"  Violations found: {len(violations)}")
        for v in violations:
            print(f"    - {v}")
    else:
        print("  No violations found.")

    return graph, violations


def _discover_functions(graph: dict, repo_path: str) -> list:
    """Dynamically import modules from *repo_path* and return callable functions.

    Uses the dependency graph produced by the Guardian to locate each Python
    module, imports it via :func:`importlib.util.spec_from_file_location`, and
    collects top-level callables whose names appear in the graph metadata.

    Args:
        graph: Dependency graph from :class:`ArchitecturalGuardian`.
        repo_path: Root path that was analyzed (added to ``sys.path``).

    .. warning::
        This function executes Python modules from the target repository.
        Only analyze repositories you trust, as arbitrary code will be run.

    Returns:
        List of discovered callable objects.
    """
    functions: list = []
    original_path = list(sys.path)
    sys.path.insert(0, repo_path)

    try:
        for file_path, info in graph.items():
            module_name = info.get("module_name", "")
            if not module_name:
                continue
            try:
                spec = importlib.util.spec_from_file_location(module_name, file_path)
                if spec is None or spec.loader is None:
                    continue
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)  # type: ignore[union-attr]

                for func_info in info.get("functions", []):
                    func_name = func_info.get("name", "")
                    obj = getattr(module, func_name, None)
                    if callable(obj) and not inspect.isclass(obj):
                        functions.append(obj)
            except Exception:  # noqa: BLE001
                continue
    finally:
        sys.path[:] = original_path

    return functions


def _run_fuzzer(graph: dict, repo_path: str) -> Optional[FuzzReport]:
    """Run the Adversarial Fuzzer pillar.

    Discovers callable functions from the analyzed repository and fuzzes
    each one, returning an aggregated :class:`FuzzReport`.

    Args:
        graph: Dependency graph from :class:`ArchitecturalGuardian`.
        repo_path: Root path of the repository.

    Returns:
        Aggregated :class:`FuzzReport`, or ``None`` if no functions were found.
    """
    print("\n[3/5] Fuzzer: Discovering functions and running fuzz tests...")
    fuzzer = AdversarialFuzzer()
    functions = _discover_functions(graph, repo_path)

    if not functions:
        print("  No functions discovered for fuzzing.")
        return None

    print(f"  Functions discovered: {len(functions)}")

    combined: Optional[FuzzReport] = None
    for func in functions:
        try:
            report = fuzzer.fuzz(func)
            if combined is None:
                combined = report
            else:
                combined.total_iterations += report.total_iterations
                combined.failures.extend(report.failures)
        except Exception:  # noqa: BLE001
            continue

    if combined is not None:
        print(f"  Total iterations: {combined.total_iterations}")
        print(f"  Crashes found: {combined.failure_count}")

    return combined


def _run_sandbox(repo_path: str) -> Optional[Any]:
    """Run the Sandbox pillar (requires Docker).

    Executes a minimal smoke-test inside an isolated Docker container to
    verify the runtime environment.

    Args:
        repo_path: Path to the repository (unused but kept for future use).

    Returns:
        :class:`~sentinel.sandbox.runner.RunResult`, or ``None`` if Docker
        is unavailable.
    """
    print("\n[4/5] Sandbox: Running tests in isolation...")
    try:
        from sentinel.sandbox import SandboxContainer, SandboxRunner  # noqa: PLC0415

        container = SandboxContainer()
        container.start()
        try:
            runner = SandboxRunner(container)
            result = runner.run_code(_SANDBOX_SMOKE_TEST, timeout=10)
            if result.exit_code == 0:
                print("  Sandbox tests passed.")
            else:
                print(f"  Sandbox tests failed (exit code: {result.exit_code}).")
                if result.stderr:
                    print(f"  stderr: {result.stderr.strip()}")
            return result
        finally:
            container.stop()
    except Exception as exc:  # noqa: BLE001
        print(f"  Warning: Sandbox not available: {exc}")
        return None


def _detect_language(graph: Dict) -> Language:
    """
    Detect the dominant language of the repository from the Guardian graph.

    Counts files by extension and returns the language with the most files.
    For mixed repos, the order of preference is Python > Java > TypeScript.

    Args:
        graph: Dependency graph from :class:`ArchitecturalGuardian`.

    Returns:
        The dominant :class:`~sentinel.core.languages.Language`.
    """
    counts: Dict[Language, int] = {
        Language.PYTHON: 0,
        Language.JAVA: 0,
        Language.TYPESCRIPT: 0,
    }
    ext_map = {
        ".py": Language.PYTHON,
        ".java": Language.JAVA,
        ".ts": Language.TYPESCRIPT,
        ".tsx": Language.TYPESCRIPT,
    }
    for file_path in graph:
        ext = os.path.splitext(file_path)[1].lower()
        lang = ext_map.get(ext)
        if lang:
            counts[lang] += 1

    if not any(counts.values()):
        return Language.UNKNOWN

    return max(counts, key=lambda l: counts[l])


def _build_policy_config(languages: List[Language]) -> PolicyConfig:
    """
    Build a :class:`PolicyConfig` that combines policies for all detected languages.

    All policies come from :mod:`sentinel.gatekeeper.policy` — the single
    source of truth for policy definitions.  Test files in ``tests/``
    contain test cases that *verify* these policies; they do not define them.

    Args:
        languages: List of languages found in the repository.

    Returns:
        A :class:`PolicyConfig` with universal + per-language policies for every
        detected language.
    """
    config = PolicyConfig.default()   # universal: NoCriticalBugs, ArchCompliance, TestPass

    for lang in languages:
        if lang is Language.PYTHON:
            for policy in PolicyConfig.for_python().policies:
                config.add_policy(policy)
        elif lang is Language.JAVA:
            for policy in PolicyConfig.for_java().policies:
                config.add_policy(policy)
        elif lang is Language.TYPESCRIPT:
            for policy in PolicyConfig.for_typescript().policies:
                config.add_policy(policy)

    return config


def _run_gatekeeper(
    historian_report: Optional[Any],
    guardian_violations: List[str],
    fuzzer_report: Optional[FuzzReport],
    sandbox_report: Optional[Any],
    graph: Optional[Dict] = None,
    config: Optional[PolicyConfig] = None,
    step_label: str = "[5/5]",
) -> Verdict:
    """
    Run the Gatekeeper pillar and return the final Verdict.

    Detects which languages are present in the repository (via the Guardian
    graph), selects the matching set of policies from
    :mod:`sentinel.gatekeeper.policy`, and evaluates all findings.

    Policies are defined in ``src/sentinel/gatekeeper/policy.py``.
    Test files in ``tests/`` contain test cases that *verify* those
    policies — they are not loaded at runtime.

    Args:
        historian_report: Stats dict from the Historian (may be ``None``).
        guardian_violations: List of violation strings from the Guardian.
        fuzzer_report: Aggregated :class:`FuzzReport` (may be ``None``).
        sandbox_report: :class:`~sentinel.sandbox.runner.RunResult` (may be
                        ``None``).
        graph: Guardian dependency graph used for language detection.

    Returns:
        :class:`~sentinel.gatekeeper.verdict.Verdict` with the final decision.
    """
    print(f"\n{step_label} Gatekeeper: Evaluating all findings...")

    # --- Detect languages present in the repo ---
    detected_langs: List[Language] = []
    if graph:
        ext_map = {
            ".py": Language.PYTHON,
            ".java": Language.JAVA,
            ".ts": Language.TYPESCRIPT,
            ".tsx": Language.TYPESCRIPT,
        }
        seen: set = set()
        for file_path in graph:
            ext = os.path.splitext(file_path)[1].lower()
            lang = ext_map.get(ext)
            if lang and lang not in seen:
                detected_langs.append(lang)
                seen.add(lang)

    if not detected_langs:
        detected_langs = [Language.UNKNOWN]

    dominant = _detect_language(graph) if graph else Language.UNKNOWN
    print(f"  Languages detected : {[l.name for l in detected_langs]}")
    print(f"  Dominant language  : {dominant.name}")

    # --- Build policy config from policy.py (not from test files) ---
    config = config or _build_policy_config(detected_langs)
    policy_names = [type(p).__name__ for p in config.policies]
    print(f"  Policies active    : {len(policy_names)}")
    for name in policy_names:
        print(f"    • {name}")

    # --- Run the Gatekeeper ---
    gatekeeper = Gatekeeper(config)
    verdict = gatekeeper.evaluate(
        historian_report=historian_report,
        guardian_report=guardian_violations if guardian_violations else None,
        fuzzer_report=fuzzer_report,
        sandbox_report=sandbox_report,
        language=dominant,
    )

    decision = "APPROVED" if verdict.approved else "REJECTED"
    print(f"  Decision           : {decision}")
    print(f"  Confidence         : {verdict.confidence:.0%}")
    if verdict.blocking_issues:
        print(f"  Blocking issues    : {len(verdict.blocking_issues)}")
        for issue in verdict.blocking_issues:
            print(f"    [!] {issue}")

    return verdict


def _print_report(
    repo_path: str,
    historian_report: Optional[Any],
    guardian_violations: List[str],
    fuzzer_report: Optional[FuzzReport],
    sandbox_report: Optional[Any],
    verdict: Verdict,
) -> None:
    """Print a structured summary report to stdout.

    Args:
        repo_path: Path that was analyzed.
        historian_report: Stats from the Historian.
        guardian_violations: Violations list from the Guardian.
        fuzzer_report: Aggregated FuzzReport.
        sandbox_report: RunResult from the Sandbox.
        verdict: Final Verdict from the Gatekeeper.
    """
    print("\n" + "=" * 60)
    print("SENTINEL ANALYSIS REPORT")
    print("=" * 60)
    print(f"Repository : {repo_path}")

    print("\n--- Historian Insights ---")
    if historian_report:
        print(f"  Commits processed : {historian_report.get('commits_processed', 0)}")
        print(f"  Total documents   : {historian_report.get('total_documents', 'n/a')}")
    else:
        print("  (unavailable — not a git repository or no commits)")

    print("\n--- Guardian Violations ---")
    if guardian_violations:
        for v in guardian_violations:
            print(f"  [!] {v}")
    else:
        print("  None")

    print("\n--- Fuzzer Results ---")
    if fuzzer_report:
        print(f"  Iterations : {fuzzer_report.total_iterations}")
        print(f"  Crashes    : {fuzzer_report.failure_count}")
        if fuzzer_report.failures:
            for inputs, exc in fuzzer_report.failures[:5]:
                print(f"    - inputs={inputs!r}  exc={exc!r}")
            if len(fuzzer_report.failures) > 5:
                print(f"    … and {len(fuzzer_report.failures) - 5} more")
    else:
        print("  (no functions fuzzed)")

    print("\n--- Sandbox ---")
    if sandbox_report is not None:
        status = "passed" if sandbox_report.exit_code == 0 else "failed"
        print(f"  Status : {status} (exit code {sandbox_report.exit_code})")
    else:
        print("  (skipped or unavailable)")

    print("\n--- Gatekeeper Verdict ---")
    decision = "APPROVED" if verdict.approved else "REJECTED"
    print(f"  Decision   : {decision}")
    print(f"  Confidence : {verdict.confidence:.0%}")
    print(f"  Summary    : {verdict.summary}")
    if verdict.blocking_issues:
        print("  Blocking issues:")
        for issue in verdict.blocking_issues:
            print(f"    [!] {issue}")
    print("=" * 60)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def _github_repo_parts(path: str) -> Optional[Tuple[str, str]]:
    match = re.match(r"https://github\.com/([^/]+)/([^/#]+?)(?:\.git)?/?$", path.strip())
    if not match:
        return None
    return match.group(1), match.group(2)


def _is_github_url(path: str) -> bool:
    return _github_repo_parts(path) is not None


def _clone_github_repo(url: str, clone_base_dir: str = "demo_project") -> str:
    repo_parts = _github_repo_parts(url)
    if repo_parts is None:
        raise ValueError(f"Unsupported GitHub URL: {url}")

    owner, repo_name = repo_parts
    clone_root = Path(clone_base_dir)
    clone_root.mkdir(parents=True, exist_ok=True)

    target_dir = clone_root / f"{owner}__{repo_name}"
    if target_dir.is_dir() and (target_dir / ".git").is_dir():
        print(f"Using existing cloned repository: {target_dir}")
        return str(target_dir.resolve())

    if target_dir.exists():
        suffix = 2
        while True:
            candidate = clone_root / f"{owner}__{repo_name}_{suffix}"
            if not candidate.exists():
                target_dir = candidate
                break
            suffix += 1

    print(f"Cloning GitHub repo {url} into {target_dir} ...")
    try:
        subprocess.run(["git", "clone", "--depth=1", url, str(target_dir)], check=True)
    except Exception as exc:
        print(f"Error: Failed to clone repo: {exc}")
        shutil.rmtree(target_dir, ignore_errors=True)
        sys.exit(1)
    return str(target_dir.resolve())


def _materialize_repo_path(repo_input: str, clone_base_dir: str = "demo_project") -> str:
    repo_path = _clone_github_repo(repo_input, clone_base_dir) if _is_github_url(repo_input) else repo_input
    repo_path = os.path.abspath(repo_path)
    if not os.path.isdir(repo_path):
        print(f"Error: '{repo_input}' is not a valid directory or GitHub repo.")
        sys.exit(1)
    return repo_path


def _report_target_name(repo_input: str, repo_path: str) -> str:
    repo_parts = _github_repo_parts(repo_input)
    if repo_parts is not None:
        return repo_parts[1]
    return Path(repo_path).name or "project"


def _default_report_path(repo_input: str, repo_path: str, prefix: str) -> Path:
    target_name = re.sub(r"[^A-Za-z0-9_.-]+", "_", _report_target_name(repo_input, repo_path))
    return Path("tests/reports") / f"{prefix}_{target_name}_{date.today().isoformat()}.txt"


def _detect_languages_in_graph(graph: Optional[Dict]) -> List[Language]:
    if not graph:
        return []

    ext_map = {
        ".py": Language.PYTHON,
        ".java": Language.JAVA,
        ".ts": Language.TYPESCRIPT,
        ".tsx": Language.TYPESCRIPT,
    }
    detected: List[Language] = []
    seen = set()
    for file_path in graph:
        lang = ext_map.get(os.path.splitext(file_path)[1].lower())
        if lang and lang not in seen:
            detected.append(lang)
            seen.add(lang)
    return detected


def _extract_json_payload(raw_text: str) -> Optional[Any]:
    text = raw_text.strip()
    if not text:
        return None

    fence_match = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    if fence_match:
        text = fence_match.group(1).strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    array_start = text.find("[")
    array_end = text.rfind("]")
    if array_start != -1 and array_end > array_start:
        try:
            return json.loads(text[array_start:array_end + 1])
        except json.JSONDecodeError:
            return None
    return None


def _request_llm_policy_suggestions(guardian_violations: List[str], languages: List[Language]) -> Tuple[Optional[str], List[Dict[str, Any]]]:
    if not guardian_violations:
        print("[Sentinel LLM] No Guardian violations were found. Skipping policy growth.")
        return None, []

    if not os.getenv("COHERE_API_KEY"):
        print("[Sentinel LLM] COHERE_API_KEY is not set. Skipping policy growth.")
        return None, []

    try:
        from sentinel.cohere_utils import call_cohere
    except ImportError:
        print("[Sentinel LLM] Cohere utility is not available. Skipping policy growth.")
        return None, []

    existing_specs = load_policy_specs_for_languages(languages)
    language_names = [language.name for language in languages] or [Language.UNKNOWN.name]
    guardian_sample = "\n".join(f"- {violation}" for violation in guardian_violations[:25])
    existing_sample = json.dumps(existing_specs, indent=2)
    prompt = (
        "Return only a JSON array of new Sentinel policy specs. "
        "Each object must have: name, language, match_mode, patterns, description. "
        "The language must be one of PYTHON, JAVA, TYPESCRIPT. "
        "The match_mode must be one of contains, casefold_contains, regex. "
        "The patterns must match Guardian violation strings directly. "
        "Do not repeat or rename existing policies. Suggest only truly new rules.\n\n"
        f"Languages in scope: {language_names}\n\n"
        f"Existing test-backed policy specs:\n{existing_sample}\n\n"
        f"Observed Guardian violations:\n{guardian_sample}\n"
    )
    messages = [
        {"role": "system", "content": "You design machine-readable static-analysis policy specs for Sentinel."},
        {"role": "user", "content": prompt},
    ]
    llm_response = call_cohere(messages)
    if not llm_response:
        print("[Sentinel LLM] No response from Cohere.")
        return None, []

    parsed = _extract_json_payload(llm_response)
    if isinstance(parsed, dict):
        parsed = [parsed]
    if not isinstance(parsed, list):
        print("[Sentinel LLM] Cohere response was not valid JSON. Skipping policy growth.")
        return llm_response, []

    suggestions = [item for item in parsed if isinstance(item, dict)]
    return llm_response, suggestions


def _print_test_report(
    repo_path: str,
    guardian_violations: List[str],
    verdict: Verdict,
    llm_response: Optional[str] = None,
    added_policy_specs: Optional[Dict[str, List[Dict[str, Any]]]] = None,
) -> None:
    print("\n" + "=" * 60)
    print("SENTINEL TEST REPORT")
    print("=" * 60)
    print(f"Repository : {repo_path}")

    print("\n--- Guardian Violations ---")
    if guardian_violations:
        for violation in guardian_violations:
            print(f"  [!] {violation}")
    else:
        print("  None")

    print("\n--- Gatekeeper Verdict ---")
    decision = "APPROVED" if verdict.approved else "REJECTED"
    print(f"  Decision   : {decision}")
    print(f"  Confidence : {verdict.confidence:.0%}")
    print(f"  Summary    : {verdict.summary}")
    if verdict.blocking_issues:
        print("  Blocking issues:")
        for issue in verdict.blocking_issues:
            print(f"    [!] {issue}")

    if llm_response is not None:
        print("\n--- LLM Policy Suggestions ---")
        if llm_response.strip():
            print(llm_response)
        else:
            print("  (no suggestions returned)")

    if added_policy_specs is not None:
        print("\n--- Policy Catalog Updates ---")
        if added_policy_specs:
            for language, entries in added_policy_specs.items():
                print(f"  {language}: {len(entries)} new policy spec(s)")
                for entry in entries:
                    print(f"    - {entry['name']}")
        else:
            print("  No policy spec updates were applied.")

    print("=" * 60)


def _run_test_workflow(repo_input: str, use_llm: bool = False, autogrow: bool = False) -> Tuple[str, Verdict]:
    repo_path = _materialize_repo_path(repo_input)
    print(f"Testing repository: {repo_path}")
    print("=" * 60)

    graph, guardian_violations = _run_guardian(repo_path, step_label="[1/2]")
    detected_langs = _detect_languages_in_graph(graph)
    config = PolicyConfig.from_languages(detected_langs)
    verdict = _run_gatekeeper(
        historian_report=None,
        guardian_violations=guardian_violations,
        fuzzer_report=None,
        sandbox_report=None,
        graph=graph,
        config=config,
        step_label="[2/2]",
    )

    llm_response: Optional[str] = None
    added_policy_specs: Optional[Dict[str, List[Dict[str, Any]]]] = None
    if use_llm:
        llm_response, suggested_specs = _request_llm_policy_suggestions(guardian_violations, detected_langs)
        print("\n--- LLM Policy Suggestions JSON ---")
        if suggested_specs:
            print(json.dumps(suggested_specs, indent=2))
        else:
            print("[]")
        print("--- End LLM Policy Suggestions JSON ---")
        if autogrow and suggested_specs:
            added_policy_specs = apply_policy_updates(suggested_specs)
        elif autogrow:
            added_policy_specs = {}

    _print_test_report(repo_path, guardian_violations, verdict, llm_response=llm_response, added_policy_specs=added_policy_specs)
    return repo_path, verdict


def _run_with_report_capture(repo_input: str, prefix: str, workflow) -> Verdict:
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        repo_path, verdict = workflow()

    output = buffer.getvalue()
    print(output, end="")

    report_path = _default_report_path(repo_input, repo_path, prefix)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(output, encoding="utf-8")
    print(f"[Sentinel] Report saved to {report_path}")
    return verdict

def analyze(repo_path: str, use_sandbox: bool = False, skip_historian: bool = False, policy_source: str = None, use_llm: bool = False) -> Verdict:
    """Analyze *repo_path* (local path or GitHub URL) by running all Sentinel pillars in sequence.
    skip_historian: if True, skip the Historian pillar and ChromaDB dependency.
    policy_source: optional path or URL to load additional/dynamic policies.
    use_llm: if True, use LLM/AI for policy suggestions and violation explanations.
    """
    orig_input = repo_path
    repo_path = _materialize_repo_path(repo_path)

    print(f"Analyzing repository: {repo_path}")
    print("=" * 60)

    # 1. Historian (optional)
    historian_report = None
    if not skip_historian:
        try:
            historian_report = _run_historian(repo_path)
        except ImportError as e:
            print(f"  [Sentinel] ChromaDB not installed or failed to import: {e}\n  Skipping Historian pillar.")
            historian_report = None
        except Exception as e:
            print(f"  [Sentinel] Historian failed: {e}\n  Skipping Historian pillar.")
            historian_report = None
    else:
        print("  [Sentinel] Historian pillar skipped by user request.")

    # 2. Guardian
    graph, guardian_violations = _run_guardian(repo_path)

    # 3. Fuzzer
    fuzzer_report = _run_fuzzer(graph, repo_path)

    # 4. Sandbox
    sandbox_report = _run_sandbox(repo_path) if use_sandbox else None

    # 5. Gatekeeper (dynamic/AI policy loading)
    # --- Dynamic/AI policy loading hook ---
    if policy_source:
        print(f"  [Sentinel] Loading additional policies from: {policy_source}")
        # TODO: Implement dynamic policy loading from file/URL/plugin
    if use_llm:
        print("  [Sentinel] Using LLM/AI for policy suggestions and violation explanations...")
        try:
            guardian_prompt = (
                "You are an expert code reviewer and static analysis policy designer. "
                "Given the following code violations, suggest new static analysis policies/rules that Sentinel could add to catch similar issues in the future. "
                "Also, briefly explain the most critical violations and how to remediate them.\n\n"
                f"Violations:\n" + '\n'.join(str(v) for v in guardian_violations[:20])
            )
            messages = [
                {"role": "system", "content": "You are a world-class static analysis and code security expert."},
                {"role": "user", "content": guardian_prompt}
            ]
            if os.getenv("COHERE_API_KEY"):
                from sentinel.cohere_utils import call_cohere
                llm_response = call_cohere(messages)
            elif os.getenv("GEMINI_API_KEY"):
                from sentinel.gemini_utils import call_gemini
                llm_response = call_gemini(messages)
            else:
                from sentinel.llm_utils import call_openai_gpt4
                llm_response = call_openai_gpt4(messages)
            if llm_response:
                print("\n--- LLM/AI Policy Suggestions & Explanations ---")
                print(llm_response)
            else:
                print("[Sentinel LLM] No response from LLM or API key missing.")
        except ImportError:
            print("[Sentinel LLM] LLM utility not available. Skipping LLM integration.")
        except Exception as e:
            print(f"[Sentinel LLM] LLM integration failed: {e}")

    verdict = _run_gatekeeper(
        historian_report, guardian_violations, fuzzer_report, sandbox_report,
        graph=graph,
    )

    _print_report(
        repo_path,
        historian_report,
        guardian_violations,
        fuzzer_report,
        sandbox_report,
        verdict,
    )

    return verdict


def test_project(repo_input: str) -> Verdict:
    """Run the Guardian + Gatekeeper-only workflow against a local path or GitHub URL."""
    return _run_with_report_capture(
        repo_input,
        prefix="test",
        workflow=lambda: _run_test_workflow(repo_input, use_llm=False, autogrow=False),
    )


def end_to_end_test(repo_input: str) -> Verdict:
    """Run the test workflow, ask Cohere for new policy specs, and grow the tests-backed policy catalog."""
    return _run_with_report_capture(
        repo_input,
        prefix="end_to_end",
        workflow=lambda: _run_test_workflow(repo_input, use_llm=True, autogrow=True),
    )

# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    """Build and return the argument parser for the Sentinel CLI."""
    parser = argparse.ArgumentParser(
        prog="sentinel",
        description="Sentinel: The Developer's Guardian — automated code analysis.",
    )
    subparsers = parser.add_subparsers(dest="command", metavar="<command>")
    subparsers.required = True

    analyze_parser = subparsers.add_parser(
        "analyze",
        help="Analyze a repository using all Sentinel pillars.",
        description=(
            "Runs the Historian, Guardian, Fuzzer, Sandbox (optional), and "
            "Gatekeeper pillars against the target repository and prints a "
            "structured report."
        ),
    )
    analyze_parser.add_argument(
        "repo_path",
        metavar="path/to/repo_or_github_url",
        help="Path to the repository to analyze (local path or GitHub URL).",
    )
    analyze_parser.add_argument(
        "--sandbox",
        action="store_true",
        default=False,
        help="Run critical tests inside an isolated Docker sandbox.",
    )
    analyze_parser.add_argument(
        "--skip-historian",
        action="store_true",
        default=False,
        help="Skip the Historian pillar and ChromaDB dependency.",
    )
    analyze_parser.add_argument(
        "--policy-source",
        type=str,
        default=None,
        help="Path or URL to load additional/dynamic policies.",
    )
    analyze_parser.add_argument(
        "--use-llm",
        action="store_true",
        default=False,
        help="Use external LLM/AI for policy suggestions and violation explanations.",
    )

    test_parser = subparsers.add_parser(
        "test",
        help="Run Sentinel's Guardian + Gatekeeper workflow against a local path or GitHub URL.",
        description=(
            "Runs the tests-backed Sentinel workflow for Python, Java, or TypeScript "
            "projects using Guardian findings and Gatekeeper policies loaded from tests/."
        ),
    )
    test_parser.add_argument(
        "repo_path",
        metavar="path/to/project_or_github_url",
        help="Path to the local project or a GitHub repository URL.",
    )

    e2e_parser = subparsers.add_parser(
        "end-to-end-test",
        help="Run the test workflow, ask Cohere for new policy specs, and autogrow tests-backed policy catalogs.",
    )
    e2e_parser.add_argument(
        "repo_path",
        metavar="path/to/project_or_github_url",
        help="Path to the local project or a GitHub repository URL.",
    )

    return parser


def main(argv: Optional[List[str]] = None) -> None:
    """Entry point for the Sentinel CLI.

    Args:
        argv: Argument list (defaults to ``sys.argv[1:]``).
    """
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "analyze":
        verdict = analyze(
            args.repo_path,
            use_sandbox=args.sandbox,
            skip_historian=args.skip_historian,
            policy_source=args.policy_source,
            use_llm=args.use_llm,
        )
        sys.exit(0 if verdict.approved else 1)
    if args.command == "test":
        verdict = test_project(args.repo_path)
        sys.exit(0 if verdict.approved else 1)
    if args.command == "end-to-end-test":
        verdict = end_to_end_test(args.repo_path)
        sys.exit(0 if verdict.approved else 1)


if __name__ == "__main__":
    main()
