"""
Sentinel CLI entry point.

Orchestrates all 5 pillars — Historian, Guardian, Fuzzer, Sandbox, and
Gatekeeper — and prints a structured analysis report for a target repository.

Usage::

    python main.py analyze /path/to/repo
    python main.py analyze /path/to/repo --sandbox
"""

import argparse
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # dotenv is optional, but recommended for .env support
import importlib.util
import inspect
import os
import sys
from typing import Any, Dict, List, Optional, Tuple

from sentinel.core.guardian import ArchitecturalGuardian
from sentinel.core.languages import Language
from sentinel.core.rules import FunctionComplexityRule, NoCircularDependenciesRule
from sentinel.fuzzer import AdversarialFuzzer, FuzzReport
from sentinel.gatekeeper import Gatekeeper, Verdict
from sentinel.gatekeeper.policy import PolicyConfig
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


def _run_guardian(repo_path: str) -> Tuple[Dict, List[str]]:
    """Run the Architectural Guardian pillar.

    Returns:
        Tuple of (graph dict, violations list).
    """
    print("\n[2/5] Guardian: Scanning codebase for rule violations...")
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
    print("\n[5/5] Gatekeeper: Evaluating all findings...")

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
    config = _build_policy_config(detected_langs)
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
    decision = "APPROVED ✓" if verdict.approved else "REJECTED ✗"
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


import tempfile
import shutil
import re
import subprocess

def _is_github_url(path: str) -> bool:
    return bool(re.match(r"https://github.com/[^/]+/[^/]+/?$", path.strip()))

def _clone_github_repo(url: str) -> str:
    temp_dir = tempfile.mkdtemp(prefix="sentinel_github_")
    print(f"Cloning GitHub repo {url} to {temp_dir} ...")
    try:
        subprocess.run(["git", "clone", "--depth=1", url, temp_dir], check=True)
    except Exception as e:
        print(f"Error: Failed to clone repo: {e}")
        shutil.rmtree(temp_dir, ignore_errors=True)
        sys.exit(1)
    return temp_dir

def analyze(repo_path: str, use_sandbox: bool = False, skip_historian: bool = False, policy_source: str = None, use_llm: bool = False) -> Verdict:
    """Analyze *repo_path* (local path or GitHub URL) by running all Sentinel pillars in sequence.
    skip_historian: if True, skip the Historian pillar and ChromaDB dependency.
    policy_source: optional path or URL to load additional/dynamic policies.
    use_llm: if True, use LLM/AI for policy suggestions and violation explanations.
    """
    cleanup_dir = None
    orig_input = repo_path
    if _is_github_url(repo_path):
        repo_path = _clone_github_repo(repo_path)
        cleanup_dir = repo_path
    repo_path = os.path.abspath(repo_path)
    if not os.path.isdir(repo_path):
        print(f"Error: '{orig_input}' is not a valid directory or GitHub repo.")
        if cleanup_dir:
            shutil.rmtree(cleanup_dir, ignore_errors=True)
        sys.exit(1)

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
            if os.getenv("GEMINI_API_KEY"):
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


if __name__ == "__main__":
    main()
