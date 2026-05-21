#!/usr/bin/env python3
"""Bootstrap and gate a compound engineering loop for Codex and Claude Code."""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import re
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple


MANAGED_START = "<!-- compound-orchestrator:start -->"
MANAGED_END = "<!-- compound-orchestrator:end -->"

REQUIRED_DIRS = [
    ".agent-loop",
    ".claude/commands",
    ".claude/agents",
    "docs/brainstorms",
    "docs/plans",
    "docs/patterns",
    "docs/decisions",
    "docs/failures",
    "docs/reviews",
    "docs/compound",
    "docs/pulse-reports",
    "scripts",
]

KIND_TO_DIR = {
    "brainstorm": "docs/brainstorms",
    "plan": "docs/plans",
    "pattern": "docs/patterns",
    "decision": "docs/decisions",
    "failure": "docs/failures",
    "review": "docs/reviews",
    "compound": "docs/compound",
    "pulse": "docs/pulse-reports",
}


@dataclass
class WriteReport:
    created: List[str] = field(default_factory=list)
    updated: List[str] = field(default_factory=list)
    skipped: List[str] = field(default_factory=list)

    def extend(self, other: "WriteReport") -> None:
        self.created.extend(other.created)
        self.updated.extend(other.updated)
        self.skipped.extend(other.skipped)

    def as_dict(self) -> Dict[str, List[str]]:
        return {
            "created": self.created,
            "updated": self.updated,
            "skipped": self.skipped,
        }


def slugify(value: str, *, max_len: int = 72) -> str:
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    value = re.sub(r"-{2,}", "-", value).strip("-")
    if not value:
        value = "task"
    return value[:max_len].rstrip("-")


def task_id_for(title: str, today: Optional[_dt.date] = None) -> str:
    today = today or _dt.date.today()
    return f"{today.isoformat()}-{slugify(title, max_len=56)}"


def rel(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def ensure_dirs(root: Path) -> WriteReport:
    report = WriteReport()
    for item in REQUIRED_DIRS:
        path = root / item
        if path.exists():
            report.skipped.append(item)
        else:
            path.mkdir(parents=True, exist_ok=True)
            report.created.append(item)
    return report


def write_file(root: Path, relative: str, content: str, *, force: bool = False) -> WriteReport:
    report = WriteReport()
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    normalized = content.strip() + "\n"
    if path.exists():
        existing = path.read_text(encoding="utf-8")
        if existing == normalized:
            report.skipped.append(relative)
            return report
        if not force:
            report.skipped.append(relative)
            return report
        path.write_text(normalized, encoding="utf-8", newline="\n")
        report.updated.append(relative)
        return report
    path.write_text(normalized, encoding="utf-8", newline="\n")
    report.created.append(relative)
    return report


def upsert_managed_block(root: Path, relative: str, title: str, body: str) -> WriteReport:
    report = WriteReport()
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    block = f"{MANAGED_START}\n{body.strip()}\n{MANAGED_END}\n"
    if path.exists():
        existing = path.read_text(encoding="utf-8")
        pattern = re.compile(
            re.escape(MANAGED_START) + r".*?" + re.escape(MANAGED_END),
            flags=re.DOTALL,
        )
        if pattern.search(existing):
            updated = pattern.sub(block.strip(), existing)
        else:
            updated = existing.rstrip() + "\n\n" + block
        if updated == existing:
            report.skipped.append(relative)
            return report
        path.write_text(updated.rstrip() + "\n", encoding="utf-8", newline="\n")
        report.updated.append(relative)
        return report
    content = f"# {title}\n\n{block}"
    path.write_text(content, encoding="utf-8", newline="\n")
    report.created.append(relative)
    return report


def common_protocol_block(tool_name: str) -> str:
    return f"""
## Compound Engineering Protocol For {tool_name}

Use this repository as a compound engineering system:

1. Start meaningful work with a task brief or plan in `docs/plans/`.
2. Keep implementation scoped to the plan unless new evidence changes it.
3. Run `scripts/verify.ps1` or the closest project-specific verification before completion.
4. Review changes for bugs, missing tests, security risks, and product regressions.
5. Record durable learning in `docs/patterns/`, `docs/decisions/`, `docs/failures/`, or `docs/compound/`.

Completion gate:

- A plan exists for the task.
- Verification was run or the blocker is documented.
- Review findings are resolved or explicitly accepted.
- A compound note records what future work should reuse or avoid.

Parallel agent policy:

- Use parallel agents for independent research, planning, test strategy, review, and competing bug hypotheses.
- Give each agent a role, scope, owned files, expected artifact, and verification responsibility.
- Avoid parallel edits to the same file unless a lead integrator owns the final merge.
"""


def strategy_template() -> str:
    return """
# Strategy

## Product Direction

- Target user:
- Primary job to be done:
- Current outcome metric:
- Constraints:

## Active Tracks

| Track | Goal | Owner | Status | Notes |
| --- | --- | --- | --- | --- |
| Compound loop | Make every task improve future execution | Lead | Active | Keep this file current |

## Decision Rules

- Prefer project patterns over new abstractions.
- Treat repeated failures as system design input.
- Promote lessons into `AGENTS.md` and `CLAUDE.md` only when they should affect future work globally.
"""


def task_brief_template() -> str:
    return """
# Task Brief

## Goal

Describe the user-visible outcome.

## Context

Relevant files, prior decisions, logs, screenshots, or constraints.

## Definition Of Done

- [ ] Implementation complete
- [ ] Tests or verification complete
- [ ] Review complete
- [ ] Compound note written

## Risks

- Risk:
- Mitigation:

## Agent Lanes

| Lane | Scope | Owned Files | Output |
| --- | --- | --- | --- |
| Lead | Synthesis and final integration | TBD | Final diff and summary |
| Research | Existing patterns and constraints | Read-only | Notes |
| Review | Bugs, tests, security, product risks | Read-only | Findings |
"""


def handoff_template() -> str:
    return """
# Agent Handoff

## Task

## Current State

## Files Touched

## Verification Run

## Open Questions

## Next Best Action
"""


def review_rubric_template() -> str:
    return """
# Review Rubric

Lead with findings. Prioritize correctness, security, user-visible regressions, missing tests, and maintainability risks.

## Required Checks

- Does the diff satisfy the plan?
- Are edge cases and failure modes covered?
- Are tests meaningful and close to the risk?
- Did the implementation follow existing project patterns?
- Did it introduce same-file ownership conflicts from parallel work?
- Should any lesson become a pattern, decision, or failure note?

## Severity

- P0: Data loss, security compromise, production outage, or unusable core path.
- P1: Incorrect behavior in important paths or high-confidence regression.
- P2: Maintainability, test, or edge-case issue that should be fixed before merge.
- P3: Small cleanup or optional polish.
"""


def scorecard_template() -> str:
    return """
# Compound Engineering Scorecard

Use this after each meaningful task.

| Date | Task | Planning Helped? | Review Caught Issues? | Reused Prior Learning? | Repeated Failure? | New Durable Note |
| --- | --- | --- | --- | --- | --- | --- |

## Questions

- Did planning reduce implementation churn?
- Did review catch a real issue?
- Did a previous compound note help?
- Did we repeat an old failure?
- What should be added to project memory?
"""


def verify_script_template() -> str:
    return r"""
param(
    [switch]$CompoundOnly
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Push-Location $Root

try {
    Write-Host "Checking compound engineering structure..."
    $required = @(
        "AGENTS.md",
        "CLAUDE.md",
        "STRATEGY.md",
        ".agent-loop/task-brief-template.md",
        ".agent-loop/review-rubric.md",
        ".agent-loop/eval-scorecard.md"
    )

    foreach ($item in $required) {
        if (-not (Test-Path -LiteralPath $item)) {
            throw "Missing required compound file: $item"
        }
    }

    if ($CompoundOnly) {
        return
    }

    if (Test-Path -LiteralPath "package.json") {
        $package = Get-Content -Raw "package.json" | ConvertFrom-Json
        if ($package.scripts.lint) { npm run lint }
        if ($package.scripts.typecheck) { npm run typecheck }
        if ($package.scripts.test) { npm test }
        if ($package.scripts.build) { npm run build }
    }

    if ((Test-Path -LiteralPath "pyproject.toml") -or (Test-Path -LiteralPath "tests")) {
        $python = if ($env:PYTHON) { $env:PYTHON } else { "python" }
        if (Test-Path -LiteralPath "tests") {
            & $python -m unittest discover -s tests -p "test_*.py"
        }
    }
}
finally {
    Pop-Location
}
"""


def claude_command_templates() -> Dict[str, str]:
    return {
        ".claude/commands/compound-start.md": """
# Compound Start

Create or update a task brief before implementation starts.

Steps:

1. Restate the goal and definition of done.
2. Inspect `STRATEGY.md`, `AGENTS.md`, `CLAUDE.md`, and relevant `docs/patterns`, `docs/decisions`, and `docs/failures`.
3. Create a plan in `docs/plans/` using `.agent-loop/task-brief-template.md`.
4. Identify parallel agent lanes only when they are independent.
5. Stop before implementation if ownership or verification is unclear.
""",
        ".claude/commands/compound-plan.md": """
# Compound Plan

Turn the current task brief into an implementation plan.

Include:

- files likely to change
- tests to add or run
- risks and mitigations
- agent lanes with disjoint ownership
- completion gate checklist
""",
        ".claude/commands/compound-review.md": """
# Compound Review

Review the current diff using `.agent-loop/review-rubric.md`.

Lead with findings. Include file and line references when possible. Call out missing verification and any lesson that should become a durable compound note.
""",
        ".claude/commands/compound-learn.md": """
# Compound Learn

Finish the task by writing durable learning.

Record at least one of:

- pattern in `docs/patterns/`
- decision in `docs/decisions/`
- failure in `docs/failures/`
- task compound note in `docs/compound/`

Update `AGENTS.md` and `CLAUDE.md` only when the lesson should affect all future work.
""",
    }


def claude_agent_templates() -> Dict[str, str]:
    return {
        ".claude/agents/compound-architect.md": """
---
name: compound-architect
description: Plans architecture and decomposition for compound engineering tasks.
tools: Read, Grep, Glob
---

You are the architecture planner. Read existing patterns before proposing new structure. Return a concise plan, risks, owned file areas, and verification strategy. Do not edit files.
""",
        ".claude/agents/compound-reviewer.md": """
---
name: compound-reviewer
description: Reviews diffs for correctness, security, regressions, tests, and compound-learning opportunities.
tools: Read, Grep, Glob, Bash
---

You are the reviewer. Lead with findings ordered by severity. Include file and line references when possible. Identify any repeated failure or missing durable note.
""",
        ".claude/agents/compound-test-runner.md": """
---
name: compound-test-runner
description: Designs and runs focused verification for a scoped task.
tools: Read, Grep, Glob, Bash
---

You own verification. Find the closest meaningful tests, run them, diagnose failures, and recommend missing coverage. Do not broaden the test surface without explaining why.
""",
    }


def init_project(root: Path, *, force: bool = False) -> WriteReport:
    root = root.resolve()
    report = ensure_dirs(root)

    report.extend(upsert_managed_block(root, "AGENTS.md", "Agent Instructions", common_protocol_block("Codex")))
    report.extend(upsert_managed_block(root, "CLAUDE.md", "Claude Instructions", common_protocol_block("Claude Code")))

    for relative, content in {
        "STRATEGY.md": strategy_template(),
        ".agent-loop/task-brief-template.md": task_brief_template(),
        ".agent-loop/handoff-template.md": handoff_template(),
        ".agent-loop/review-rubric.md": review_rubric_template(),
        ".agent-loop/eval-scorecard.md": scorecard_template(),
        "scripts/verify.ps1": verify_script_template(),
        **claude_command_templates(),
        **claude_agent_templates(),
    }.items():
        report.extend(write_file(root, relative, content, force=force))

    return report


def task_plan_content(task_id: str, title: str) -> str:
    return f"""
# {title}

Task id: `{task_id}`

## Goal

## Context Consulted

- `STRATEGY.md`
- `AGENTS.md`
- `CLAUDE.md`
- `docs/patterns/`
- `docs/decisions/`
- `docs/failures/`

## Plan

- [ ] Understand existing patterns
- [ ] Implement scoped change
- [ ] Add or update verification
- [ ] Review diff
- [ ] Write compound note

## Verification

- Command:
- Result:

## Parallel Agent Lanes

| Agent | Scope | Owned Files | Artifact |
| --- | --- | --- | --- |
"""


def brainstorm_content(task_id: str, title: str) -> str:
    return f"""
# Brainstorm: {title}

Task id: `{task_id}`

## Ideas

## Constraints

## Open Questions

## Selected Direction
"""


def start_task(root: Path, title: str, *, today: Optional[_dt.date] = None, force: bool = False) -> Tuple[str, WriteReport]:
    root = root.resolve()
    task_id = task_id_for(title, today=today)
    report = ensure_dirs(root)
    report.extend(write_file(root, f"docs/brainstorms/{task_id}.md", brainstorm_content(task_id, title), force=force))
    report.extend(write_file(root, f"docs/plans/{task_id}.md", task_plan_content(task_id, title), force=force))
    return task_id, report


def note_content(kind: str, title: str, summary: str, task_id: Optional[str]) -> str:
    date = _dt.date.today().isoformat()
    task_line = f"Task id: `{task_id}`\n" if task_id else ""
    prompts = {
        "pattern": "## Reuse Rule\n\nWhen this situation appears again, future agents should:\n",
        "decision": "## Decision\n\n## Alternatives Rejected\n\n## Consequences\n",
        "failure": "## Root Cause\n\n## Fix\n\n## Prevention Rule\n",
        "review": "## Findings\n\n## Verification\n\n## Follow-Up\n",
        "compound": "## What Compounded\n\n## Future Prompting Or Process Change\n",
        "pulse": "## Product Signal\n\n## Recommended Adjustment\n",
        "brainstorm": "## Ideas\n\n## Selected Direction\n",
        "plan": "## Plan\n\n## Verification\n",
    }
    return f"""
# {title}

Date: `{date}`
Kind: `{kind}`
{task_line}
## Summary

{summary}

{prompts[kind]}
"""


def learn(root: Path, *, kind: str, title: str, summary: str, task_id: Optional[str], force: bool = False) -> Tuple[str, WriteReport]:
    if kind not in KIND_TO_DIR:
        raise ValueError(f"Unknown note kind: {kind}")
    root = root.resolve()
    note_id = task_id if task_id and kind in {"review", "compound", "plan", "brainstorm"} else slugify(title)
    relative = f"{KIND_TO_DIR[kind]}/{note_id}.md"
    report = ensure_dirs(root)
    report.extend(write_file(root, relative, note_content(kind, title, summary, task_id), force=force))
    return relative, report


def check_project(root: Path, task_id: Optional[str] = None) -> Tuple[bool, List[str]]:
    root = root.resolve()
    failures: List[str] = []

    for item in REQUIRED_DIRS:
        if not (root / item).is_dir():
            failures.append(f"Missing directory: {item}")

    required_files = [
        "AGENTS.md",
        "CLAUDE.md",
        "STRATEGY.md",
        ".agent-loop/task-brief-template.md",
        ".agent-loop/handoff-template.md",
        ".agent-loop/review-rubric.md",
        ".agent-loop/eval-scorecard.md",
        "scripts/verify.ps1",
        ".claude/commands/compound-start.md",
        ".claude/commands/compound-plan.md",
        ".claude/commands/compound-review.md",
        ".claude/commands/compound-learn.md",
        ".claude/agents/compound-architect.md",
        ".claude/agents/compound-reviewer.md",
        ".claude/agents/compound-test-runner.md",
    ]
    for item in required_files:
        if not (root / item).is_file():
            failures.append(f"Missing file: {item}")

    for item in ["AGENTS.md", "CLAUDE.md"]:
        path = root / item
        if path.exists():
            text = path.read_text(encoding="utf-8")
            if MANAGED_START not in text or MANAGED_END not in text:
                failures.append(f"Missing managed compound block in {item}")

    if task_id:
        task_files = [
            f"docs/plans/{task_id}.md",
            f"docs/reviews/{task_id}.md",
            f"docs/compound/{task_id}.md",
        ]
        for item in task_files:
            if not (root / item).is_file():
                failures.append(f"Task gate missing file: {item}")

    return not failures, failures


def self_test(plugin_root: Path) -> Tuple[bool, List[str]]:
    failures: List[str] = []
    plugin_root = plugin_root.resolve()
    codex_manifest = plugin_root / ".codex-plugin/plugin.json"
    if not codex_manifest.exists():
        failures.append("Missing .codex-plugin/plugin.json")
    else:
        try:
            codex_data = json.loads(codex_manifest.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            failures.append(f"Invalid Codex plugin manifest JSON: {exc}")
            codex_data = {}
        for key in ["name", "version", "description", "skills", "interface"]:
            if key not in codex_data:
                failures.append(f"Codex manifest missing key: {key}")
        codex_manifest_text = codex_manifest.read_text(encoding="utf-8")
        if "[TODO:" in codex_manifest_text:
            failures.append("Codex manifest still contains TODO placeholders")
        skills_path = plugin_root / codex_data.get("skills", "").replace("./", "")
        if codex_data.get("skills") and not skills_path.exists():
            failures.append(f"Codex manifest skills path does not exist: {codex_data.get('skills')}")

    claude_manifest = plugin_root / ".claude-plugin/plugin.json"
    if not claude_manifest.exists():
        failures.append("Missing .claude-plugin/plugin.json")
    else:
        try:
            claude_data = json.loads(claude_manifest.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            failures.append(f"Invalid Claude plugin manifest JSON: {exc}")
            claude_data = {}
        for key in ["name", "version", "description"]:
            if key not in claude_data:
                failures.append(f"Claude manifest missing key: {key}")
        claude_manifest_text = claude_manifest.read_text(encoding="utf-8")
        if "[TODO:" in claude_manifest_text:
            failures.append("Claude manifest still contains TODO placeholders")
        for default_dir in ["commands", "agents", "skills"]:
            if not (plugin_root / default_dir).is_dir():
                failures.append(f"Claude default component path does not exist: {default_dir}")

    for required in [
        "README.md",
        "LICENSE",
        "skills/compound-orchestrator/SKILL.md",
        "scripts/verify_plugin.ps1",
        "scripts/verify_plugin.sh",
        "commands/compound-init.md",
        "commands/compound-start.md",
        "commands/compound-plan.md",
        "commands/compound-review.md",
        "commands/compound-learn.md",
        "agents/compound-architect.agent.md",
        "agents/compound-reviewer.agent.md",
        "agents/compound-test-runner.agent.md",
    ]:
        if not (plugin_root / required).exists():
            failures.append(f"Missing plugin file: {required}")

    with tempfile.TemporaryDirectory() as tmp:
        target = Path(tmp) / "target"
        target.mkdir()
        init_project(target)
        ok, check_failures = check_project(target)
        if not ok:
            failures.extend(f"bootstrap check: {item}" for item in check_failures)
        task_id, _ = start_task(target, "Exercise recursive improvement loop", today=_dt.date(2026, 5, 21))
        learn(
            target,
            kind="review",
            title="Review exercise recursive improvement loop",
            summary="No blocking findings in self-test fixture.",
            task_id=task_id,
            force=False,
        )
        learn(
            target,
            kind="compound",
            title="Compound exercise recursive improvement loop",
            summary="The plugin can create the artifacts required by its own gate.",
            task_id=task_id,
            force=False,
        )
        ok, check_failures = check_project(target, task_id=task_id)
        if not ok:
            failures.extend(f"task gate check: {item}" for item in check_failures)

    return not failures, failures


def print_report(report: WriteReport, *, json_output: bool = False, extra: Optional[Dict[str, str]] = None) -> None:
    if json_output:
        payload = report.as_dict()
        if extra:
            payload.update(extra)
        print(json.dumps(payload, indent=2, sort_keys=True))
        return
    if extra:
        for key, value in extra.items():
            print(f"{key}: {value}")
    for label, values in [("created", report.created), ("updated", report.updated), ("skipped", report.skipped)]:
        if values:
            print(f"{label}:")
            for value in values:
                print(f"  - {value}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Bootstrap and gate a compound engineering workflow.")
    sub = parser.add_subparsers(dest="command", required=True)

    init_p = sub.add_parser("init", help="Install compound engineering files into a target project.")
    init_p.add_argument("--target", default=".", help="Project root to initialize.")
    init_p.add_argument("--force", action="store_true", help="Overwrite generated non-managed files.")
    init_p.add_argument("--json", action="store_true", help="Print JSON report.")

    check_p = sub.add_parser("check", help="Check compound engineering structure and optional task gate.")
    check_p.add_argument("--target", default=".", help="Project root to check.")
    check_p.add_argument("--task-id", help="Require plan, review, and compound files for this task id.")
    check_p.add_argument("--json", action="store_true", help="Print JSON report.")

    start_p = sub.add_parser("start", help="Create brainstorm and plan artifacts for a task.")
    start_p.add_argument("--target", default=".", help="Project root.")
    start_p.add_argument("--title", required=True, help="Task title.")
    start_p.add_argument("--force", action="store_true", help="Overwrite existing generated task files.")
    start_p.add_argument("--json", action="store_true", help="Print JSON report.")

    learn_p = sub.add_parser("learn", help="Write a durable compound engineering note.")
    learn_p.add_argument("--target", default=".", help="Project root.")
    learn_p.add_argument("--kind", required=True, choices=sorted(KIND_TO_DIR), help="Note kind.")
    learn_p.add_argument("--title", required=True, help="Note title.")
    learn_p.add_argument("--summary", required=True, help="Short summary for future agents.")
    learn_p.add_argument("--task-id", help="Task id to link the note to.")
    learn_p.add_argument("--force", action="store_true", help="Overwrite an existing note.")
    learn_p.add_argument("--json", action="store_true", help="Print JSON report.")

    self_p = sub.add_parser("self-test", help="Validate the plugin package and bootstrap behavior.")
    self_p.add_argument("--root", default=".", help="Plugin root.")
    self_p.add_argument("--json", action="store_true", help="Print JSON result.")

    return parser


def main(argv: Optional[Iterable[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)

    if args.command == "init":
        report = init_project(Path(args.target), force=args.force)
        print_report(report, json_output=args.json)
        return 0

    if args.command == "check":
        ok, failures = check_project(Path(args.target), task_id=args.task_id)
        if args.json:
            print(json.dumps({"ok": ok, "failures": failures}, indent=2, sort_keys=True))
        elif ok:
            print("compound gate: PASS")
        else:
            print("compound gate: FAIL")
            for failure in failures:
                print(f"  - {failure}")
        return 0 if ok else 1

    if args.command == "start":
        task_id, report = start_task(Path(args.target), args.title, force=args.force)
        print_report(report, json_output=args.json, extra={"task_id": task_id})
        return 0

    if args.command == "learn":
        note_path, report = learn(
            Path(args.target),
            kind=args.kind,
            title=args.title,
            summary=args.summary,
            task_id=args.task_id,
            force=args.force,
        )
        print_report(report, json_output=args.json, extra={"note": note_path})
        return 0

    if args.command == "self-test":
        ok, failures = self_test(Path(args.root))
        if args.json:
            print(json.dumps({"ok": ok, "failures": failures}, indent=2, sort_keys=True))
        elif ok:
            print("plugin self-test: PASS")
        else:
            print("plugin self-test: FAIL")
            for failure in failures:
                print(f"  - {failure}")
        return 0 if ok else 1

    parser.error(f"Unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
