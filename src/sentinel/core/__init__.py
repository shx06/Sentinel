"""
Core module for Sentinel.

Contains the scanner, rule engine, and Architectural Guardian.
"""

from .guardian import ArchitecturalGuardian
from .rules import (
    FunctionComplexityRule,
    JavaNamingConventionRule,
    MaxFunctionLinesRule,
    MissingJavadocRule,
    NoCircularDependenciesRule,
    NoConsoleLogRule,
    NoUnsafeTypeAssertionRule,
    PublicFieldRule,
    RequireDocstringRule,
    Rule,
    TODOCommentRule,
)
from .scanner import CodeScanner

__all__ = [
    "ArchitecturalGuardian",
    "CodeScanner",
    # Rules
    "Rule",
    "FunctionComplexityRule",
    "NoCircularDependenciesRule",
    # Python rules
    "MaxFunctionLinesRule",
    "RequireDocstringRule",
    "TODOCommentRule",
    # Java rules
    "JavaNamingConventionRule",
    "MissingJavadocRule",
    "PublicFieldRule",
    # TypeScript rules
    "NoConsoleLogRule",
    "NoUnsafeTypeAssertionRule",
]
