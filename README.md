# Sentinel: The Developer's Guardian

## Vision

**"No software developer, only innovator"**

Sentinel transforms the software development experience by automating the mechanical aspects of coding, allowing developers to focus on innovation and creative problem-solving. It serves as an intelligent guardian that maintains code quality, prevents regressions, and ensures architectural integrity while developers concentrate on building the future.

## The 5 Pillars

### 1. Contextual Historian (Memory & Context)
Sentinel maintains a deep understanding of your codebase's evolution, tracking changes, decisions, and patterns over time. It provides context-aware insights that help teams understand not just *what* changed, but *why* and *how* it impacts the broader system.

### 2. Architectural Guardian (Structure & Rules)
Acts as a vigilant protector of your system's architectural principles and design patterns. Sentinel identifies violations, suggests improvements, and ensures that new code adheres to established architectural standards, preventing technical debt from accumulating.

### 3. Adversarial Fuzzer (Adversarial Testing)
Proactively discovers edge cases, vulnerabilities, and potential failures by generating intelligent test cases and adversarial inputs. Sentinel explores the boundaries of your code to find issues before they reach production.

### 4. Autonomous Sandbox (Isolated Execution)
Provides isolated, reproducible environments for testing and experimentation. Sentinel can automatically spin up sandboxes, execute tests, and validate changes in controlled environments without manual intervention.

### 5. Principled Gatekeeper (Executive Decision)
Enforces quality standards, security policies, and best practices with unwavering consistency. Sentinel acts as the final checkpoint, ensuring that only code meeting defined criteria makes it into your codebase.

Historian learns the project history.
Guardian checks the architecture.
Fuzzer attacks the functions.
Sandbox runs the tests safely.
Gatekeeper issues a PASS/FAIL verdict.

## Tech Stack

- **Python**: Core implementation language
- **LangGraph**: Agent orchestration and workflow management
- **Tree-sitter**: Code parsing and analysis
- **Docker**: Containerization and sandbox environments
- **ChromaDB**: Vector storage for semantic code search
- **Pytest**: Testing framework
- **Ruff**: Fast Python linting and formatting

## Current Workflow

Sentinel now exposes two project-testing workflows for local paths and GitHub repository URLs:

- `python -m sentinel.cli test <path-or-github-url>`
- `python -m sentinel.cli end-to-end-test <path-or-github-url>`

The normal `test` workflow runs only the Architectural Guardian and the Principled Gatekeeper. It does not invoke Historian, Fuzzer, Sandbox, or LLM policy growth.

The active runtime policies for Python, Java, and TypeScript are loaded from:

- `src/sentinel/gatekeeper/policies/policy_specs.json`

Test files in `tests/` validate policy behavior, but runtime policy loading is independent from the tests folder.

The `end-to-end-test` workflow runs the same Guardian + Gatekeeper flow, then asks Cohere for additional machine-readable policy specs. Any new specs are merged back into `src/sentinel/gatekeeper/policies/policy_specs.json` so Sentinel's policy coverage can grow over time.

When a GitHub URL is provided, Sentinel clones the repository into the `demo_project/` folder and runs the workflow against that local checkout.
