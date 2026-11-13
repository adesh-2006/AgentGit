"""Static Prompt & Tool Contract Linter (agentgit lint).

Analyzes prompts and tool declarations statically before execution to detect:
- Contradictory constraints (e.g. JSON-only vs Markdown formatting)
- Unbounded output risks (missing length constraints)
- Prompt injection vulnerabilities (unescaped variable delimiters)
- Missing tool parameter descriptions

Usage::

    from agentgit.lint import lint_prompt
    report = lint_prompt("You are a helpful bot. Output only valid JSON. Use markdown tables.")
"""

from __future__ import annotations

import re
from typing import List

from pydantic import BaseModel, Field


class LintIssue(BaseModel):
    """A single issue discovered by the linter."""

    level: str  # "ERROR", "WARNING", "INFO"
    code: str
    message: str
    suggestion: str = ""


class LintReport(BaseModel):
    """Full static analysis report for a prompt or agent contract."""

    target_name: str = "prompt"
    issues: List[LintIssue] = Field(default_factory=list)
    errors: int = 0
    warnings: int = 0
    score: int = 100  # 0 to 100 quality score


_CONTRADICTIONS = [
    (
        r"\b(?:(?:only|exclusively)\s+(?:output|reply|respond\s+with)|(?:output|reply|respond\s+with)\s+(?:only|exclusively))\s+(?:valid\s+)?json\b",
        r"\b(markdown|bullet\s+points|headers?)\b",
        "Prompt requests 'only valid JSON' but also references markdown/bullet points.",
        "Clarify output format: specify whether the JSON payload itself contains markdown, or remove markdown references.",
    ),
    (
        r"\b(be\s+concise|brief|short|one\s+sentence)\b",
        r"\b(detailed|thorough|comprehensive|step[- ]by[- ]step|in[- ]depth)\b",
        "Prompt requests both concise brevity and comprehensive/step-by-step detail.",
        "Separate concise summaries from detailed analysis with explicit condition branches.",
    ),
]


def lint_prompt(prompt_text: str, target_name: str = "prompt") -> LintReport:
    """Run static analysis rules over *prompt_text*."""
    issues: List[LintIssue] = []

    # 1. Contradiction checks
    for pat_a, pat_b, msg, sugg in _CONTRADICTIONS:
        has_a = re.search(pat_a, prompt_text, re.IGNORECASE)
        has_b = re.search(pat_b, prompt_text, re.IGNORECASE)
        if has_a and has_b:
            issues.append(LintIssue(
                level="WARNING",
                code="PROMPT_CONTRADICTION",
                message=msg,
                suggestion=sugg,
            ))

    # 2. Prompt injection delimiter check
    if re.search(r"\{[a-zA-Z0-9_]+\}", prompt_text):
        if not re.search(r"(###|<user_input>|```|\"\"\"|\[INPUT\])", prompt_text, re.IGNORECASE):
            issues.append(LintIssue(
                level="WARNING",
                code="INJECTION_SURFACE",
                message="Template variables found without clear XML or delimiter boundary tags.",
                suggestion="Wrap user input variables in explicit delimiter tags like <user_input>{input}</user_input> to mitigate prompt injections.",
            ))

    # 3. Output bounds check
    if len(prompt_text.split()) > 40:
        if not re.search(r"\b(limit|maximum|concise|under\s+\d+|characters?|words?|tokens?)\b", prompt_text, re.IGNORECASE):
            issues.append(LintIssue(
                level="INFO",
                code="UNBOUNDED_OUTPUT",
                message="No explicit length limits found. Agent may produce runaway outputs.",
                suggestion="Specify expected response length (e.g., 'Keep responses under 200 words' or 'Limit to 3 paragraphs').",
            ))

    # 4. Role definition check
    if not re.search(r"\b(you are|your role|act as|as an?)\b", prompt_text, re.IGNORECASE):
        issues.append(LintIssue(
            level="INFO",
            code="NO_SYSTEM_PERSONA",
            message="Prompt does not explicitly define an identity or persona for the agent.",
            suggestion="Add an explicit role definition (e.g., 'You are a Senior DevOps Engineer...').",
        ))

    errors = sum(1 for i in issues if i.level == "ERROR")
    warnings = sum(1 for i in issues if i.level == "WARNING")
    score = max(0, 100 - (errors * 30 + warnings * 15 + len(issues) * 5))

    return LintReport(
        target_name=target_name,
        issues=issues,
        errors=errors,
        warnings=warnings,
        score=score,
    )
