#!/usr/bin/env python3
"""Bootstrap and gate a compound engineering loop for Codex and Claude Code."""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple


MANAGED_START = "<!-- compound-orchestrator:start -->"
MANAGED_END = "<!-- compound-orchestrator:end -->"

REQUIRED_DIRS = [
    ".agent-loop",
    ".agent-loop/coordination",
    ".claude/commands",
    ".claude/agents",
    "docs/brainstorms",
    "docs/plans",
    "docs/patterns",
    "docs/decisions",
    "docs/failures",
    "docs/reviews",
    "docs/cross-reviews",
    "docs/compound",
    "docs/pulse-reports",
    "scripts",
]

CLAUDE_AGENT_TEAM_ENV = "CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS"

DEFAULT_PERMISSION_DENY = [
    "Read(./.env)",
    "Read(./.env.*)",
    "Read(./.git/**)",
    "Read(./node_modules/**)",
    "Read(./dist/**)",
    "Read(./build/**)",
    "Read(./coverage/**)",
    "Read(./.next/**)",
    "Read(./vendor/**)",
    "Read(./generated/**)",
    "Read(./**/*.min.js)",
    "Read(./**/*.map)",
]

KIND_TO_DIR = {
    "brainstorm": "docs/brainstorms",
    "plan": "docs/plans",
    "pattern": "docs/patterns",
    "decision": "docs/decisions",
    "failure": "docs/failures",
    "review": "docs/reviews",
    "cross-review": "docs/cross-reviews",
    "compound": "docs/compound",
    "pulse": "docs/pulse-reports",
}

OWNERSHIP_FILE = ".agent-loop/coordination/ownership.json"
SUGGESTED_TOOL_NAMES = ["claude", "codex", "cursor", "aider", "other"]
TOOL_NAME_RE = re.compile(r"^[a-z][a-z0-9_-]{1,39}$")

CORE_PLANNING_ARTIFACTS = [
    "prd.html",
    "planning.html",
    "spec.html",
    "test-cases.html",
    "architecture.html",
    "users.html",
]

CROSS_REVIEW_STAGES = [
    "round-1-review",
    "round-1-response",
    "round-2-review",
    "round-2-response",
    "final-acceptance",
]


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


class OwnershipConflict(Exception):
    def __init__(self, conflicts: List[Dict[str, str]]) -> None:
        self.conflicts = conflicts
        super().__init__("ownership conflict")


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


def now_iso() -> str:
    return _dt.datetime.now(_dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def normalize_scope_path(value: str) -> str:
    value = value.strip().replace("\\", "/")
    value = re.sub(r"/+", "/", value)
    if value.startswith("./"):
        value = value[2:]
    value = value.strip("/")
    return value or "."


def paths_overlap(left: str, right: str) -> bool:
    left = normalize_scope_path(left)
    right = normalize_scope_path(right)
    if left == "." or right == ".":
        return True
    if "*" in left or "?" in left or "[" in left:
        return left == right or right.startswith(left.split("*", 1)[0].rstrip("/") + "/")
    if "*" in right or "?" in right or "[" in right:
        return left == right or left.startswith(right.split("*", 1)[0].rstrip("/") + "/")
    return left == right or left.startswith(right + "/") or right.startswith(left + "/")


def validate_tool_name(tool: str, *, field: str = "tool") -> str:
    normalized = tool.strip().lower()
    if not TOOL_NAME_RE.match(normalized):
        raise ValueError(f"{field} must be 2-40 lowercase letters, numbers, underscores, or hyphens")
    return normalized


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


def write_json_file(root: Path, relative: str, data: Dict[str, object]) -> WriteReport:
    report = WriteReport()
    path = root / relative
    serialized = json.dumps(data, indent=2, sort_keys=True) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        existing = path.read_text(encoding="utf-8")
        if existing == serialized:
            report.skipped.append(relative)
            return report
        path.write_text(serialized, encoding="utf-8", newline="\n")
        report.updated.append(relative)
        return report
    path.write_text(serialized, encoding="utf-8", newline="\n")
    report.created.append(relative)
    return report


def load_ownership(root: Path) -> Dict[str, object]:
    path = root / OWNERSHIP_FILE
    if not path.exists():
        return {"schema_version": 1, "claims": []}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"{OWNERSHIP_FILE} is not valid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"{OWNERSHIP_FILE} must contain a JSON object")
    claims = data.get("claims")
    if claims is None:
        data["claims"] = []
    elif not isinstance(claims, list):
        raise ValueError(f"{OWNERSHIP_FILE}.claims must be a JSON array")
    data.setdefault("schema_version", 1)
    return data


def save_ownership(root: Path, data: Dict[str, object]) -> WriteReport:
    return write_json_file(root, OWNERSHIP_FILE, data)


def claim_scope(
    root: Path,
    *,
    tool: str,
    agent: str,
    task_id: str,
    paths: List[str],
    intent: str = "",
    force: bool = False,
) -> WriteReport:
    tool = validate_tool_name(tool)
    if not paths:
        raise ValueError("at least one path must be claimed")
    root = root.resolve()
    ensure_dirs(root)
    data = load_ownership(root)
    claims = data["claims"]
    normalized_paths = [normalize_scope_path(item) for item in paths]

    conflicts: List[Dict[str, str]] = []
    for requested in normalized_paths:
        for claim in claims:
            if not isinstance(claim, dict) or claim.get("status") != "active":
                continue
            same_claimant = claim.get("tool") == tool and claim.get("agent") == agent and claim.get("task_id") == task_id
            if same_claimant:
                continue
            existing_path = str(claim.get("path", ""))
            if paths_overlap(existing_path, requested):
                conflicts.append(
                    {
                        "requested_path": requested,
                        "existing_path": existing_path,
                        "existing_tool": str(claim.get("tool", "")),
                        "existing_agent": str(claim.get("agent", "")),
                        "existing_task_id": str(claim.get("task_id", "")),
                    }
                )
    if conflicts and not force:
        raise OwnershipConflict(conflicts)

    existing_keys = {
        (
            claim.get("tool"),
            claim.get("agent"),
            claim.get("task_id"),
            claim.get("path"),
            claim.get("status"),
        )
        for claim in claims
        if isinstance(claim, dict)
    }
    timestamp = now_iso()
    for path_value in normalized_paths:
        key = (tool, agent, task_id, path_value, "active")
        if key in existing_keys:
            continue
        claims.append(
            {
                "tool": tool,
                "agent": agent,
                "task_id": task_id,
                "path": path_value,
                "intent": intent,
                "status": "active",
                "claimed_at": timestamp,
            }
        )
    return save_ownership(root, data)


def release_scope(
    root: Path,
    *,
    tool: Optional[str] = None,
    agent: Optional[str] = None,
    task_id: Optional[str] = None,
    paths: Optional[List[str]] = None,
) -> Tuple[int, WriteReport]:
    root = root.resolve()
    if tool:
        tool = validate_tool_name(tool)
    data = load_ownership(root)
    normalized_paths = [normalize_scope_path(item) for item in (paths or [])]
    released = 0
    timestamp = now_iso()
    for claim in data.get("claims", []):
        if not isinstance(claim, dict) or claim.get("status") != "active":
            continue
        if tool and claim.get("tool") != tool:
            continue
        if agent and claim.get("agent") != agent:
            continue
        if task_id and claim.get("task_id") != task_id:
            continue
        if normalized_paths and normalize_scope_path(str(claim.get("path", ""))) not in normalized_paths:
            continue
        claim["status"] = "released"
        claim["released_at"] = timestamp
        released += 1
    return released, save_ownership(root, data)


def active_claims(root: Path) -> List[Dict[str, object]]:
    data = load_ownership(root.resolve())
    return [claim for claim in data.get("claims", []) if isinstance(claim, dict) and claim.get("status") == "active"]


def active_ownership_conflicts(root: Path) -> List[Dict[str, str]]:
    claims = active_claims(root)
    conflicts: List[Dict[str, str]] = []
    for index, left in enumerate(claims):
        for right in claims[index + 1 :]:
            same_claimant = (
                left.get("tool") == right.get("tool")
                and left.get("agent") == right.get("agent")
                and left.get("task_id") == right.get("task_id")
            )
            if same_claimant:
                continue
            if paths_overlap(str(left.get("path", "")), str(right.get("path", ""))):
                conflicts.append(
                    {
                        "left_path": str(left.get("path", "")),
                        "left_tool": str(left.get("tool", "")),
                        "left_agent": str(left.get("agent", "")),
                        "right_path": str(right.get("path", "")),
                        "right_tool": str(right.get("tool", "")),
                        "right_agent": str(right.get("agent", "")),
                    }
                )
    return conflicts


def merge_claude_settings(root: Path) -> WriteReport:
    relative = ".claude/settings.json"
    path = root / relative
    existed = path.exists()
    if existed:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"{relative} is not valid JSON: {exc}") from exc
        if not isinstance(data, dict):
            raise ValueError(f"{relative} must contain a JSON object")
    else:
        data = {
            "$schema": "https://json.schemastore.org/claude-code-settings.json",
        }

    env = data.get("env")
    if env is None:
        env = {}
    if not isinstance(env, dict):
        raise ValueError(f"{relative}.env must be a JSON object when present")
    env[CLAUDE_AGENT_TEAM_ENV] = "1"
    data["env"] = env

    permissions = data.get("permissions")
    if permissions is None:
        permissions = {}
    if not isinstance(permissions, dict):
        raise ValueError(f"{relative}.permissions must be a JSON object when present")

    deny = permissions.get("deny")
    if deny is None:
        deny = []
    if not isinstance(deny, list):
        raise ValueError(f"{relative}.permissions.deny must be a JSON array when present")
    for item in DEFAULT_PERMISSION_DENY:
        if item not in deny:
            deny.append(item)
    permissions["deny"] = deny
    data["permissions"] = permissions

    return write_json_file(root, relative, data)


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


def upsert_readme(root: Path) -> WriteReport:
    relative = "README.md"
    path = root / relative
    if path.exists():
        return upsert_managed_block(root, relative, "Project", readme_maintenance_block())

    block = f"{MANAGED_START}\n{readme_maintenance_block().strip()}\n{MANAGED_END}\n"
    content = project_readme_starter().strip() + "\n\n" + block
    return write_file(root, relative, content, force=False)


def copy_orchestrator_script(root: Path, *, force: bool = False) -> WriteReport:
    source = Path(__file__).resolve()
    return write_file(root, "scripts/compound_orchestrator.py", source.read_text(encoding="utf-8"), force=force)


def common_protocol_block(tool_name: str) -> str:
    return f"""
## Compound Engineering Protocol For {tool_name}

Use this repository as a compound engineering system for coding, writing, research, documentation, or mixed project work:

1. Start meaningful work with a task brief or plan in `docs/plans/`.
2. For substantial projects, complete the six planning contracts: `prd.html`, `planning.html`, `spec.html`, `test-cases.html`, `architecture.html`, and `users.html`.
3. Keep implementation scoped to the plan unless new evidence changes it.
4. Run `scripts/verify.py`, `scripts/verify.ps1`, `scripts/verify.sh`, or the closest project-specific verification before completion.
5. Review changes for bugs, missing tests, security risks, product regressions, factual drift, stale documentation, and unclear writing.
6. Record durable learning in `docs/patterns/`, `docs/decisions/`, `docs/failures/`, or `docs/compound/`.
7. Keep `README.md` current by removing stale information, preserving still-true information, adding new content, and reorganizing it into an easy-to-follow narrative.

Completion gate:

- A plan exists for the task.
- The six planning contracts are accepted before implementation starts on substantial projects.
- Any files edited by Claude Code or Codex are claimed in `.agent-loop/coordination/ownership.json` before edits.
- No active ownership claim overlaps another agent's claim unless the lead explicitly resolves the conflict.
- A cross-tool review exists when Claude Code reviews Codex-authored changes or Codex reviews Claude-authored changes.
- Verification was run or the blocker is documented.
- Two cross-review rounds are complete and author responses are recorded; stop after two rounds unless the user asks for more.
- `README.md` reflects the latest project state when the task changes setup, usage, architecture, workflow, output, or audience-facing behavior.
- A compound note records what future work should reuse or avoid.

Parallel agent policy:

- Use `.agent-loop/team-topology.md` as the shared Claude/Codex team contract.
- Use parallel agents for independent research, planning, test strategy, review, and competing bug hypotheses.
- Parallelize planning drafts, then serialize integration, `spec.html`, `test-cases.html`, and final acceptance.
- Give each agent a role, scope, owned files, expected artifact, and verification responsibility.
- Avoid parallel edits to the same file unless a lead integrator owns the final merge.
- Claude Code should use agent teams when work benefits from teammate-to-teammate coordination.
- Codex should mirror the same team shape with a lead-integrator hub plus explorer/worker/reviewer agents; workers must have disjoint write scopes.
- Before editing, claim intended files with `compound_orchestrator.py claim`.
- Before handing off, release claims with `compound_orchestrator.py release` or document why they remain active.
- Use the opposite tool's reviewer for cross-tool review: Claude reviews Codex-authored changes, Codex reviews Claude-authored changes, and other agents use the same author/reviewer split.

Project harness rules:

- Keep root `CLAUDE.md` short: big picture, navigation pointers, and critical gotchas only.
- Put local build/test/lint commands in subdirectory `CLAUDE.md` files.
- Start Claude Code in the subdirectory where work is happening; parent `CLAUDE.md` files still load.
- Move repeated procedural instructions into path-scoped skills instead of bloating `CLAUDE.md`.
- Prefer hooks over "always remember to..." instructions when behavior should be automatic.
"""


def readme_maintenance_block() -> str:
    return """
## README Maintenance

Treat `README.md` as part of the product, not as a stale landing page.

When a task changes setup, usage, architecture, workflow, commands, generated outputs, public behavior, or the intended audience:

1. Remove outdated information.
2. Keep information that is still true, reorganizing it when needed.
3. Add the new information readers need.
4. Do a final pass so the README is easy to follow and reflects the latest project state.

For writing projects, keep the README aligned with the current manuscript, outline, sources, export process, and review workflow.

For coding projects, keep the README aligned with install, run, test, architecture, deployment, and troubleshooting reality.
"""


def readme_maintenance_template() -> str:
    return """
# README Maintenance Guide

Use this guide for every coding, writing, research, or mixed project created by Compound Orchestrator.

## Update Rule

Update `README.md` whenever work changes:

- setup or installation
- commands or verification
- architecture or project layout
- user-facing behavior
- writing scope, manuscript structure, export process, or review workflow
- agent workflow, ownership, or project conventions

## Edit Process

1. Remove old information that is no longer true.
2. Keep unchanged information that is still useful.
3. Add new content required by the latest work.
4. Reorganize the README into a coherent narrative.
5. Verify examples, commands, and paths.

## Suggested Shape

- What this project is
- Who it is for
- Current status
- Quick start
- Project layout
- Daily workflow
- Verification
- Agent workflow
- Maintenance notes
"""


def project_readme_starter() -> str:
    return """
# Project

This project is managed with Compound Orchestrator.

## Current Status

Describe the current project state, audience, and primary outcome.

## Quick Start

Add the commands or steps needed to work with this project.

## Project Layout

See `CODEBASE_MAP.md` for the lightweight map of important directories.

## Agent Workflow

Use the compound loop:

```text
brainstorm -> plan -> work -> review -> compound
```

Before multi-agent edits, claim files with:

```bash
python scripts/compound_orchestrator.py claim --target . --tool codex --agent AGENT --task-id TASK --paths path/to/file
```

## Verification

Use the cross-platform verifier:

```bash
python scripts/verify.py
```
"""


def strategy_template() -> str:
    return """
# Strategy

## Project Direction

- Audience or user:
- Primary outcome:
- Current artifact:
- Success signal:
- Constraints:

## Active Tracks

| Track | Goal | Owner | Status | Notes |
| --- | --- | --- | --- | --- |
| Compound loop | Make every task improve future execution | Lead | Active | Keep this file current |

## Decision Rules

- Prefer project patterns over new abstractions.
- Treat repeated failures as system design input.
- Promote lessons into `AGENTS.md` and `CLAUDE.md` only when they should affect future work globally.
- Review the Claude/Codex harness every 3-6 months and after major model releases.
"""


def task_brief_template() -> str:
    return """
# Task Brief

## Goal

Describe the user-visible or reader-visible outcome.

## Context

Relevant files, prior decisions, logs, screenshots, or constraints.

Start Claude Code from the most specific subdirectory for this task when using Claude. Root context will still load through the parent walk, and local `CLAUDE.md` files should provide scoped commands.

## Definition Of Done

- [ ] Work product complete
- [ ] Tests or verification complete
- [ ] Review complete
- [ ] `README.md` updated if setup, usage, architecture, workflow, outputs, or audience-facing behavior changed
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

Lead with findings. Prioritize correctness, security, user-visible or reader-visible regressions, missing tests, factual drift, stale documentation, and maintainability risks.

## Required Checks

- Does the diff satisfy the plan?
- Are edge cases and failure modes covered?
- Are tests meaningful and close to the risk?
- Did the implementation follow existing project patterns?
- Did it introduce same-file ownership conflicts from parallel work?
- Did active agent claims overlap in `.agent-loop/coordination/ownership.json`?
- Did the opposite tool review the change when both tools participated?
- Is `README.md` current and easy to follow after the change?
- For writing work, are claims, sources, outline, terminology, and export instructions still accurate?
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
- Should a repeated instruction become a hook or path-scoped skill?
- Should a root instruction move into a subdirectory `CLAUDE.md`?
"""


def codebase_map_template() -> str:
    return """
# Project Map

Keep this file lightweight. One line per top-level area is enough. For large areas, create another `CODEBASE_MAP.md` or `CLAUDE.md` deeper in the tree.

| Path | Purpose | Local Context |
| --- | --- | --- |
| `.agent-loop/` | Compound engineering templates and gates | `.agent-loop/harness-checklist.md` |
| `.claude/` | Claude Code project commands, agents, settings, and optional skills | `.claude/settings.json` |
| `docs/` | Durable decisions, patterns, failures, plans, reviews, and compound notes | `docs/compound/` |
| `scripts/` | Project verification and automation entrypoints | `scripts/verify.py` |
| `src/` or app folders | Product code, services, packages, or app surfaces | Add local `CLAUDE.md` when commands differ |
| `drafts/`, `manuscript/`, or writing folders | Writing project source material, chapters, essays, reports, or exports | Add local context for outline, sources, and review rules |
"""


def harness_checklist_template() -> str:
    return """
# Project Harness Checklist

Use this checklist when setting up or reviewing the Claude/Codex/agent harness for coding, writing, research, documentation, or mixed projects.

## Foundation

- [ ] One DRI owns settings, permissions, marketplace/plugin updates, and `CLAUDE.md` conventions.
- [ ] Root `CLAUDE.md` is short: big picture, navigation pointers, and critical gotchas.
- [ ] Subdirectory `CLAUDE.md` files capture local build, test, lint, and naming conventions.
- [ ] Developers start Claude Code in the subdirectory they are changing.
- [ ] `CODEBASE_MAP.md` points to top-level areas and deeper local context.
- [ ] `README.md` is current, reader-friendly, and includes the managed README maintenance policy.

## Automation

- [ ] `.claude/settings.json` denies generated, vendored, build, coverage, secret, and dependency paths.
- [ ] Hooks handle automatic checks or improvement prompts instead of relying on memory.
- [ ] Stop hook proposes `CLAUDE.md` or durable-memory updates when a session learns something reusable.
- [ ] Verification entrypoint exists and is scoped enough to avoid full-suite overuse.
- [ ] `scripts/verify.py`, `scripts/verify.ps1`, and `scripts/verify.sh` work on the platforms the team uses.

## Skills And Plugins

- [ ] Repeated task-specific expertise lives in skills, not root `CLAUDE.md`.
- [ ] Skills are path-scoped by placing them in the relevant subtree when possible.
- [ ] The baseline setup is packaged as a plugin so new engineers get it on day one.

## Code Intelligence And Integrations

- [ ] LSP is planned or installed for typed languages where grep is too noisy.
- [ ] MCP servers are added only after the context layer, skills, hooks, and ownership are healthy.
- [ ] Internal MCP integrations have an owner, auth model, and failure mode.

## Maintenance

- [ ] Harness review happens every 3-6 months and after major model releases.
- [ ] Dead instructions and obsolete hooks are removed.
- [ ] README updates remove obsolete information, keep still-true information, add new content, and reorganize the narrative.
- [ ] Repeated failures become docs, tests, hooks, or skills.
"""


def module_claude_template() -> str:
    return """
# Subdirectory CLAUDE.md Template

Copy this into a service, package, chapter, manuscript section, research area, or module as `CLAUDE.md`. Keep it local and specific.

## Purpose

What this area owns in one or two sentences.

## Local Commands

- Build:
- Unit test:
- Focused test:
- Lint:
- Typecheck:
- Draft/export/check:

## Local Conventions

- Naming:
- Error handling:
- Data/model boundaries:
- Generated files:
- Source/citation rules:

## Gotchas

- Critical gotcha:

## Local Skills

If this module has specialized workflows, place path-scoped skills under:

```text
<this-module>/.claude/skills/<skill-name>/SKILL.md
```
"""


def path_scoped_skill_template() -> str:
    return """
# Path-Scoped Skill Template

Place this under the relevant subtree:

```text
services/payments/.claude/skills/payments-deploy/SKILL.md
```

Use a path-scoped skill when the expertise applies to one module or task type and would bloat root `CLAUDE.md`.

```markdown
---
name: payments-deploy
description: Use when deploying or reviewing deployment changes for the payments service.
---

# Payments Deploy

## When To Use

Use for payments deployment, rollback, and post-deploy validation.

## Required Context

- Local `CLAUDE.md`
- Service runbook
- Recent deployment notes

## Workflow

1. Check branch and diff scope.
2. Run focused tests.
3. Verify migration/backfill risk.
4. Prepare deploy or rollback notes.
5. Record any durable learning in `docs/`.
```
"""


def lsp_mcp_roadmap_template() -> str:
    return """
# LSP And MCP Roadmap

Add these after the context layer, hooks, and skills are healthy.

## LSP Candidates

| Language | Server | Install Owner | Status | Notes |
| --- | --- | --- | --- | --- |
| Python | pyright | TBD | Candidate | Useful when symbol names collide |
| TypeScript | typescript-language-server | TBD | Candidate | Useful in monorepos |
| Java/C#/C++ | language-specific server | TBD | Candidate | High value in typed enterprise repos |

## MCP Candidates

| Tool/Data Source | Why Claude Needs It | Owner | Auth Model | Status |
| --- | --- | --- | --- | --- |
| Internal docs | Avoid stale local knowledge | TBD | TBD | Backlog |
| Ticketing system | Link work to source of truth | TBD | TBD | Backlog |
| Analytics/logs | Debug with live operational context | TBD | TBD | Backlog |
| Source library or reference manager | Keep writing projects grounded in current source material | TBD | TBD | Backlog |

## Rule

Do not add MCP servers just because they are available. Add them when repeated work is blocked by information an agent cannot reach through the repo, docs, or normal tools.
"""


def ownership_template() -> str:
    return """
# Harness Ownership

## DRI

- Name:
- Backup:
- Review cadence:
- Last review:
- Next review:

## Scope

The DRI owns:

- `CLAUDE.md` conventions
- `.claude/settings.json`
- permissions policy
- plugin marketplace and updates
- path-scoped skill standards
- hook safety and usefulness
- LSP/MCP rollout decisions

## Review Triggers

- Every 3-6 months
- After major model releases
- When developer feedback plateaus
- After repeated failures or recurring review comments
"""


def team_topology_template() -> str:
    return """
# Compound Agent Team Topology

Use this file as the shared operating contract for Claude Code agent teams and Codex parallel-agent runs.

## Default Team

| Role | Claude Code Teammate Type | Codex Role | Scope | Output |
| --- | --- | --- | --- | --- |
| Lead Integrator | lead session | local lead | Plan, assign, synthesize, integrate | Final diff and summary |
| PRD Agent | task-specific teammate | worker | Product requirements contract | `prd.html` |
| Users Agent | task-specific teammate | worker | User roles and workflows | `users.html` |
| Architect | `compound-architect` | explorer | Existing patterns, design, risks | Architecture notes |
| Planning Agent | task-specific teammate | worker | Delivery plan | `planning.html` |
| Spec Agent | task-specific teammate | worker | Behavior, state, data, validation, and acceptance contract | `spec.html` |
| Test Case Agent | `compound-test-runner` | worker/explorer | Happy paths, edge cases, errors, performance, workflows | `test-cases.html` |
| Implementer | task-specific teammate | worker | Bounded work product with owned files | Patch, draft, or handoff |
| Test Runner | `compound-test-runner` | worker/explorer | Verification strategy and execution | Test results |
| Reviewer | `compound-reviewer` | explorer/reviewer | Correctness, security, tests, product risk | Findings |
| Claude Cross-Tool Reviewer | `compound-cross-tool-reviewer` | n/a | Review Codex-authored changes | Cross-tool findings |
| Codex Cross-Tool Reviewer | n/a | `codex-cross-tool-reviewer` skill | Review Claude-authored changes | Cross-tool findings |
| Compound Writer | lead or reviewer | local lead | Durable learning | Pattern, decision, failure, or compound note |

## When To Use A Team

Use a team for:

- dependency-aware planning across PRD, users, architecture, planning, spec, and tests
- research and review
- competing debugging hypotheses
- new modules with separable ownership
- writing or research sections with separable claims, sources, or review lanes
- cross-layer work where frontend, backend, and tests can be owned separately

Do not use a team for:

- tiny fixes
- sequential migrations
- same-file edits
- work without a clear verification path

## Claude Code Team Rules

- `.claude/settings.json` must set `env.CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS` to `"1"`.
- Ask Claude to create an agent team in natural language; Claude creates the runtime team config itself.
- Reuse plugin or project agent definitions as teammate types.
- Start with 3-5 teammates and give each teammate a scoped task.
- Use `compound-cross-tool-reviewer` when reviewing work authored by Codex or another agent runtime.
- Keep runtime team files under `~/.claude/teams/` untouched; they are managed by Claude Code.

## Codex Parallel-Agent Rules

- The lead Codex session owns decomposition, final synthesis, and integration.
- Spawn agents only for independent work that materially advances the task.
- Give every spawned agent: role, goal, read/write scope, output artifact, and verification responsibility.
- Workers that edit files must have disjoint ownership.
- Explorer/reviewer agents should be read-only unless explicitly assigned a patch.
- The lead should not redo delegated work; integrate results and fill gaps.
- Use the `codex-cross-tool-reviewer` skill when reviewing work authored by Claude Code or another agent runtime.
- Planning runs should parallelize independent drafts, then serialize integration, `spec.html`, `test-cases.html`, two-round review, and final acceptance.

## Ownership Claims

Before edits, claim files, directories, drafts, or artifacts:

```bash
python scripts/compound_orchestrator.py claim --tool codex --agent codex-worker --task-id TASK --paths src/payments.py tests/test_payments.py --intent "Implement retry handling"
```

The claim fails if another active Claude or Codex agent already owns an overlapping path. Release claims when done:

```bash
python scripts/compound_orchestrator.py release --tool codex --agent codex-worker --task-id TASK
```

## Shared Handoff

Every team run should leave a note in `docs/compound/` with:

- task id
- team members and scopes
- files owned by each agent
- ownership conflicts and resolutions
- verification run
- review findings
- cross-tool review result
- two-round review responses and final acceptance
- lessons promoted to patterns, decisions, or failures
"""


def codex_parallel_contract_template() -> str:
    return """
# Codex Parallel-Agent Contract

Codex does not use Claude Code's runtime team config. It should mirror the same compound team topology with a lead-agent hub.

## Lead Responsibilities

- Decide whether parallel agents are useful.
- Keep the immediate blocking task local.
- Delegate bounded sidecar tasks with clear scopes.
- Prevent overlapping write ownership.
- Claim intended write paths in `.agent-loop/coordination/ownership.json` before edits.
- Refuse to edit files actively claimed by another agent runtime unless the lead releases or explicitly resolves the claim.
- Integrate returned work and run verification.
- Request Claude `compound-cross-tool-reviewer` review for Codex-authored changes when Claude Code is part of the workflow.
- Run Codex `codex-cross-tool-reviewer` review for Claude-authored changes before integration.
- Record durable learning before completion.

## Delegation Prompt Template

```text
You are not alone in this project. Other agents may be working in parallel.

Runtime or tool label:
Role:
Goal:
Owned files, modules, drafts, or artifacts:
Read-only context:
Output artifact:
Verification responsibility:
Do not edit outside your ownership scope.
Do not revert unrelated changes.
Before editing, claim owned files with `compound_orchestrator.py claim`.
If the claim fails, stop and report the conflict.
List changed files and remaining risks in your final answer.
```

## Recommended Parallel Lanes

- PRD: `prd.html`.
- Users/workflow: `users.html`.
- Architecture: `architecture.html` and `architecture.excalidraw`.
- Planning: `planning.html`.
- Spec: `spec.html` after integration.
- Test cases: `test-cases.html` after `spec.html`.
- Explorer: read-only project pattern research.
- Architect: plan decomposition and risks.
- Worker: bounded implementation, writing, or documentation in owned files.
- Test Runner: test design, execution, failure diagnosis.
- Reviewer: diff review against `.agent-loop/review-rubric.md`.

## Completion Gate

A Codex team run is complete only when the lead has:

- synthesized agent outputs
- confirmed no active cross-tool ownership conflict remains
- completed the opposite-tool review when more than one agent runtime participated
- completed both cross-review rounds and author responses
- resolved or accepted review findings
- run verification or documented the blocker
- written a compound note under `docs/compound/`
"""


def cross_tool_protocol_template() -> str:
    return """
# Cross-Tool Conflict And Review Protocol

Use this protocol whenever Claude Code, Codex, or another agent runtime may work in the same repository.

## Conflict Prevention

1. Every editing agent claims its intended files or directories before editing.
2. Claims live in `.agent-loop/coordination/ownership.json`.
3. A claim fails when it overlaps another active claim from a different agent or tool.
4. The lead integrator resolves conflicts by narrowing scopes, releasing old claims, or serializing the work.
5. Agents release claims after their patch is integrated, abandoned, or handed off.

## Cross-Tool Review

- Claude Code uses `compound-cross-tool-reviewer` to review Codex-authored changes.
- Codex uses `codex-cross-tool-reviewer` to review Claude-authored changes.
- Cross-review findings and responses are written to `docs/cross-reviews/<task-id>/`.
- The required stages are `round-1-review.md`, `round-1-response.md`, `round-2-review.md`, `round-2-response.md`, and `final-acceptance.md`.
- A task involving both tools should not finish until both review rounds and author responses are complete.
- Stop after two rounds unless the user explicitly asks for more.
- Planning reviews must cover `prd.html`, `planning.html`, `spec.html`, `test-cases.html`, `architecture.html`, and `users.html`.

## Commands

```bash
python scripts/compound_orchestrator.py claim --tool codex --agent codex-worker --task-id TASK --paths src/foo.py
python scripts/compound_orchestrator.py ownership-status --target .
python scripts/compound_orchestrator.py cross-review --target . --task-id TASK --reviewer-tool codex --author-tool claude --stage round-1-review --summary "Round 1 findings."
python scripts/compound_orchestrator.py cross-review --target . --task-id TASK --reviewer-tool claude --author-tool codex --stage round-1-response --summary "Author addressed round 1."
python scripts/compound_orchestrator.py release --tool codex --agent codex-worker --task-id TASK
```
"""


def core_planning_artifacts_template() -> str:
    return """
# Core Planning Artifacts

These six HTML files are the planning contract for substantial coding, writing, research, and mixed projects:

1. `prd.html` - product requirements, scope, success criteria, non-goals.
2. `planning.html` - delivery phases, dependencies, ownership, sequencing.
3. `spec.html` - detailed behavior, states, data contracts, validation, errors, edge conditions, and acceptance criteria.
4. `test-cases.html` - happy paths, edge cases, error cases, performance cases, user workflow cases, and acceptance mapping derived from `spec.html`.
5. `architecture.html` - components, boundaries, data flow, dependencies, deployment, failure modes, and an Excalidraw-compatible diagram reference.
6. `users.html` - user roles, journeys, permissions, outcomes, and operational handoffs.

Implementation should not begin until these artifacts are internally consistent and accepted through the two-round cross-review protocol.

## Dependency-Aware Planning Flow

1. Parallel draft `prd.html`, `users.html`, `architecture.html`, `planning.html`, and early test risks.
2. Lead integrator reconciles scope, workflows, architecture, plan, and test risks.
3. Write `spec.html` from the accepted PRD, users, architecture, and planning artifacts.
4. Write `test-cases.html` from `spec.html`.
5. Run two cross-review rounds and record final acceptance.
"""


def two_round_review_protocol_template() -> str:
    return """
# Two-Round Cross-Review Protocol

`compound-cross-review` is a two-round review contract, not a one-note ritual.

For each task, keep these files under `docs/cross-reviews/<task-id>/`:

1. `round-1-review.md`
2. `round-1-response.md`
3. `round-2-review.md`
4. `round-2-response.md`
5. `final-acceptance.md`

Codex reviews Claude-authored work, Claude addresses comments, Codex reviews again, and Claude addresses the second round. For Codex-authored work, invert the reviewer and author tools. Stop after two rounds unless the user explicitly asks for more.

For planning gates, each review and response should cover all six artifacts:

- `prd.html`
- `planning.html`
- `spec.html`
- `test-cases.html`
- `architecture.html`
- `users.html`
"""


def parallel_agent_team_protocol_template() -> str:
    return """
# Parallel Agent Team Protocol

Parallelize independent planning and verification work, then serialize integration and acceptance.

## Phase A: Parallel Drafting

| Agent | Owns | Output |
| --- | --- | --- |
| PRD agent | `prd.html` | Product contract |
| Users/workflow agent | `users.html` | User and workflow contract |
| Architecture agent | `architecture.html`, `architecture.excalidraw` | System contract and diagram |
| Planning agent | `planning.html` | Delivery plan |
| Test strategy agent | Initial risks for `test-cases.html` | Test categories |

## Phase B: Integration

The lead integrator reconciles assumptions before spec work begins.

## Phase C: Spec

The spec agent writes `spec.html` from accepted PRD, users, architecture, and planning artifacts.

## Phase D: Tests

The test-case agent writes `test-cases.html` from `spec.html`.

## Phase E: Review

Run the two-round cross-review protocol before implementation begins.

Every editing agent claims files before edits. Failed claims stop the work until the lead narrows scope, releases stale claims, or serializes the task.
"""


def deliverables_checklist_template() -> str:
    return """
# Deliverables Checklist

Use this before implementation and before final delivery.

## Planning Contracts

- [ ] `prd.html` complete
- [ ] `planning.html` complete
- [ ] `spec.html` complete
- [ ] `test-cases.html` maps to `spec.html`
- [ ] `architecture.html` references `architecture.excalidraw`
- [ ] `users.html` complete

## Two-Round Cross Review

- [ ] `docs/cross-reviews/<task-id>/round-1-review.md`
- [ ] `docs/cross-reviews/<task-id>/round-1-response.md`
- [ ] `docs/cross-reviews/<task-id>/round-2-review.md`
- [ ] `docs/cross-reviews/<task-id>/round-2-response.md`
- [ ] `docs/cross-reviews/<task-id>/final-acceptance.md`

## Delivery Evidence

- [ ] Verification commands and results recorded
- [ ] README updated or explicitly marked unaffected
- [ ] Residual manual checks documented
- [ ] Deployment/push blockers documented
- [ ] Compound learning recorded
"""


def planning_html_template(filename: str) -> str:
    titles = {
        "prd.html": "Product Requirements Document",
        "planning.html": "Implementation Planning Contract",
        "spec.html": "Functional And Technical Specification",
        "test-cases.html": "Test Cases And Acceptance Matrix",
        "architecture.html": "Architecture Contract",
        "users.html": "Users And Workflow Contract",
    }
    body = {
        "prd.html": """
      <section><h2>Problem</h2><p>State the problem, target users, business context, scope, non-goals, and measurable success criteria.</p></section>
      <section><h2>Requirements</h2><ul><li>Functional requirements</li><li>Quality requirements</li><li>Operational requirements</li><li>Constraints and assumptions</li></ul></section>
""",
        "planning.html": """
      <section><h2>Delivery Plan</h2><p>Define phases, milestones, dependencies, ownership, sequencing, risks, and verification gates.</p></section>
      <section><h2>Agent Lanes</h2><p>Use dependency-aware parallel planning, then serialize integration and acceptance.</p></section>
""",
        "spec.html": """
      <section><h2>Behavior Contract</h2><p>Define states, inputs, outputs, data contracts, validation, errors, edge conditions, performance expectations, and acceptance criteria.</p></section>
      <section><h2>Traceability</h2><p>Link every behavior to PRD, users, architecture, and planning decisions.</p></section>
""",
        "test-cases.html": """
      <section><h2>Source Specification</h2><p>Tests are derived from <a href=\"spec.html\">spec.html</a>.</p></section>
      <section><h2>Coverage Matrix</h2><ul><li>Happy paths</li><li>Edge cases</li><li>Error cases</li><li>Performance cases</li><li>User workflow cases</li><li>Acceptance criteria</li></ul></section>
""",
        "architecture.html": """
      <section><h2>Architecture Diagram</h2><p>Open the Excalidraw-compatible diagram: <a href=\"architecture.excalidraw\">architecture.excalidraw</a>.</p></section>
      <section><h2>System Boundaries</h2><p>Document components, data flow, dependencies, deployment shape, failure modes, observability, and security boundaries.</p></section>
""",
        "users.html": """
      <section><h2>User Roles</h2><p>Document primary users, secondary users, administrators, operators, and external systems.</p></section>
      <section><h2>Workflows</h2><p>Map journeys, permissions, handoffs, pain points, expected outcomes, and support paths.</p></section>
""",
    }
    return f"""<!doctype html>
<html lang=\"en\">
  <head>
    <meta charset=\"utf-8\">
    <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">
    <title>{titles[filename]}</title>
    <style>
      body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; line-height: 1.55; margin: 2rem; max-width: 980px; }}
      header, section {{ margin-bottom: 1.5rem; }}
      code {{ background: #f3f4f6; padding: 0.1rem 0.25rem; border-radius: 4px; }}
      table {{ border-collapse: collapse; width: 100%; }}
      th, td {{ border: 1px solid #d1d5db; padding: 0.5rem; text-align: left; vertical-align: top; }}
    </style>
  </head>
  <body>
    <header>
      <h1>{titles[filename]}</h1>
      <p>Generated by Compound Orchestrator. Replace template text with project-specific contracts before implementation.</p>
    </header>
{body[filename]}
    <section>
      <h2>Two-Round Review Trace</h2>
      <table>
        <thead><tr><th>Stage</th><th>Status</th><th>Notes</th></tr></thead>
        <tbody>
          <tr><td>Round 1 review</td><td>Pending</td><td>Record in <code>docs/cross-reviews/&lt;task-id&gt;/round-1-review.md</code>.</td></tr>
          <tr><td>Round 1 response</td><td>Pending</td><td>Authoring tool addresses comments.</td></tr>
          <tr><td>Round 2 review</td><td>Pending</td><td>Reviewer checks revisions.</td></tr>
          <tr><td>Round 2 response</td><td>Pending</td><td>Authoring tool addresses second round.</td></tr>
          <tr><td>Final acceptance</td><td>Pending</td><td>Implementation may begin after acceptance.</td></tr>
        </tbody>
      </table>
    </section>
  </body>
</html>"""


def architecture_excalidraw_template() -> str:
    return json.dumps(
        {
            "type": "excalidraw",
            "version": 2,
            "source": "compound-orchestrator",
            "elements": [
                {"id": "users", "type": "rectangle", "x": 20, "y": 80, "width": 160, "height": 80, "angle": 0, "strokeColor": "#1f2937", "backgroundColor": "#dbeafe", "fillStyle": "solid", "strokeWidth": 2, "strokeStyle": "solid", "roughness": 1, "opacity": 100, "groupIds": [], "frameId": None, "roundness": {"type": 3}, "seed": 1, "version": 1, "versionNonce": 1, "isDeleted": False, "boundElements": [], "updated": 1, "link": None, "locked": False},
                {"id": "app", "type": "rectangle", "x": 260, "y": 80, "width": 180, "height": 80, "angle": 0, "strokeColor": "#1f2937", "backgroundColor": "#dcfce7", "fillStyle": "solid", "strokeWidth": 2, "strokeStyle": "solid", "roughness": 1, "opacity": 100, "groupIds": [], "frameId": None, "roundness": {"type": 3}, "seed": 2, "version": 1, "versionNonce": 2, "isDeleted": False, "boundElements": [], "updated": 1, "link": None, "locked": False},
                {"id": "services", "type": "rectangle", "x": 520, "y": 80, "width": 200, "height": 80, "angle": 0, "strokeColor": "#1f2937", "backgroundColor": "#fef3c7", "fillStyle": "solid", "strokeWidth": 2, "strokeStyle": "solid", "roughness": 1, "opacity": 100, "groupIds": [], "frameId": None, "roundness": {"type": 3}, "seed": 3, "version": 1, "versionNonce": 3, "isDeleted": False, "boundElements": [], "updated": 1, "link": None, "locked": False},
                {"id": "users-text", "type": "text", "x": 55, "y": 105, "width": 90, "height": 25, "angle": 0, "strokeColor": "#111827", "backgroundColor": "transparent", "fillStyle": "solid", "strokeWidth": 1, "strokeStyle": "solid", "roughness": 1, "opacity": 100, "groupIds": [], "frameId": None, "roundness": None, "seed": 4, "version": 1, "versionNonce": 4, "isDeleted": False, "boundElements": [], "updated": 1, "link": None, "locked": False, "text": "Users", "fontSize": 20, "fontFamily": 1, "textAlign": "center", "verticalAlign": "middle", "containerId": None, "originalText": "Users", "lineHeight": 1.25},
                {"id": "app-text", "type": "text", "x": 287, "y": 105, "width": 130, "height": 25, "angle": 0, "strokeColor": "#111827", "backgroundColor": "transparent", "fillStyle": "solid", "strokeWidth": 1, "strokeStyle": "solid", "roughness": 1, "opacity": 100, "groupIds": [], "frameId": None, "roundness": None, "seed": 5, "version": 1, "versionNonce": 5, "isDeleted": False, "boundElements": [], "updated": 1, "link": None, "locked": False, "text": "Application", "fontSize": 20, "fontFamily": 1, "textAlign": "center", "verticalAlign": "middle", "containerId": None, "originalText": "Application", "lineHeight": 1.25},
                {"id": "services-text", "type": "text", "x": 552, "y": 105, "width": 135, "height": 25, "angle": 0, "strokeColor": "#111827", "backgroundColor": "transparent", "fillStyle": "solid", "strokeWidth": 1, "strokeStyle": "solid", "roughness": 1, "opacity": 100, "groupIds": [], "frameId": None, "roundness": None, "seed": 6, "version": 1, "versionNonce": 6, "isDeleted": False, "boundElements": [], "updated": 1, "link": None, "locked": False, "text": "Services / Data", "fontSize": 20, "fontFamily": 1, "textAlign": "center", "verticalAlign": "middle", "containerId": None, "originalText": "Services / Data", "lineHeight": 1.25},
            ],
            "appState": {"gridSize": None, "viewBackgroundColor": "#ffffff"},
            "files": {},
        },
        indent=2,
    )


def verify_py_template() -> str:
    return r"""
#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional


MANAGED_START = "<!-- compound-orchestrator:start -->"
MANAGED_END = "<!-- compound-orchestrator:end -->"
CLAUDE_AGENT_TEAM_ENV = "CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS"

REQUIRED_FILES = [
    "README.md",
    "AGENTS.md",
    "CLAUDE.md",
    "CODEBASE_MAP.md",
    "STRATEGY.md",
    ".agent-loop/task-brief-template.md",
    ".agent-loop/handoff-template.md",
    ".agent-loop/review-rubric.md",
    ".agent-loop/eval-scorecard.md",
    ".agent-loop/harness-checklist.md",
    ".agent-loop/module-claude-template.md",
    ".agent-loop/path-scoped-skill-template.md",
    ".agent-loop/lsp-mcp-roadmap.md",
    ".agent-loop/harness-ownership.md",
    ".agent-loop/team-topology.md",
    ".agent-loop/codex-parallel-contract.md",
    ".agent-loop/cross-tool-protocol.md",
    ".agent-loop/core-planning-artifacts.md",
    ".agent-loop/two-round-review-protocol.md",
    ".agent-loop/parallel-agent-team-protocol.md",
    ".agent-loop/deliverables-checklist.md",
    ".agent-loop/readme-maintenance.md",
    ".agent-loop/coordination/ownership.json",
    "prd.html",
    "planning.html",
    "spec.html",
    "test-cases.html",
    "architecture.html",
    "architecture.excalidraw",
    "users.html",
    ".claude/settings.json",
    ".claude/commands/compound-start.md",
    ".claude/commands/compound-plan.md",
    ".claude/commands/compound-review.md",
    ".claude/commands/compound-learn.md",
    ".claude/commands/compound-init.md",
    ".claude/commands/compound-team-start.md",
    ".claude/commands/compound-harness-check.md",
    ".claude/commands/compound-claim.md",
    ".claude/commands/compound-release.md",
    ".claude/commands/compound-ownership-status.md",
    ".claude/commands/compound-cross-review.md",
    ".claude/commands/compound-deliverables-check.md",
    ".claude/agents/compound-architect.md",
    ".claude/agents/compound-reviewer.md",
    ".claude/agents/compound-test-runner.md",
    ".claude/agents/compound-cross-tool-reviewer.md",
    "scripts/compound_orchestrator.py",
    "scripts/verify.py",
    "scripts/verify.ps1",
    "scripts/verify.sh",
]

IGNORED_PARTS = {
    ".git",
    ".hg",
    ".svn",
    ".venv",
    "__pycache__",
    "node_modules",
    "dist",
    "build",
    "coverage",
    ".next",
    "vendor",
    "generated",
}


def normalize_scope_path(value: str) -> str:
    value = value.strip().replace("\\", "/")
    while "//" in value:
        value = value.replace("//", "/")
    if value.startswith("./"):
        value = value[2:]
    value = value.strip("/")
    return value or "."


def paths_overlap(left: str, right: str) -> bool:
    left = normalize_scope_path(left)
    right = normalize_scope_path(right)
    if left == "." or right == ".":
        return True
    if "*" in left or "?" in left or "[" in left:
        return left == right or right.startswith(left.split("*", 1)[0].rstrip("/") + "/")
    if "*" in right or "?" in right or "[" in right:
        return left == right or left.startswith(right.split("*", 1)[0].rstrip("/") + "/")
    return left == right or left.startswith(right + "/") or right.startswith(left + "/")


def load_json(path: Path, errors: List[str]) -> Optional[object]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        errors.append(f"Invalid JSON in {path}: {exc}")
    return None


def verify_compound(root: Path) -> List[str]:
    errors: List[str] = []

    for item in REQUIRED_FILES:
        if not (root / item).is_file():
            errors.append(f"Missing required compound file: {item}")

    for item in ["README.md", "AGENTS.md", "CLAUDE.md"]:
        path = root / item
        if path.exists():
            text = path.read_text(encoding="utf-8")
            if MANAGED_START not in text or MANAGED_END not in text:
                errors.append(f"Missing managed compound block in {item}")

    readme_policy = root / ".agent-loop/readme-maintenance.md"
    if readme_policy.exists():
        text = readme_policy.read_text(encoding="utf-8")
        for phrase in ["Remove old information", "Keep unchanged information", "Add new content", "Reorganize"]:
            if phrase not in text:
                errors.append(f"README maintenance guide is missing policy phrase: {phrase}")

    architecture_html = root / "architecture.html"
    if architecture_html.exists():
        text = architecture_html.read_text(encoding="utf-8").lower()
        if "excalidraw" not in text or "architecture.excalidraw" not in text:
            errors.append("architecture.html must reference architecture.excalidraw")
    architecture_diagram = root / "architecture.excalidraw"
    if architecture_diagram.exists():
        diagram = load_json(architecture_diagram, errors)
        if isinstance(diagram, dict) and diagram.get("type") != "excalidraw":
            errors.append("architecture.excalidraw must have type=excalidraw")
    test_cases = root / "test-cases.html"
    if test_cases.exists():
        text = test_cases.read_text(encoding="utf-8").lower()
        for phrase in ["spec.html", "happy", "edge", "error", "performance", "user workflow", "acceptance"]:
            if phrase not in text:
                errors.append(f"test-cases.html must map coverage to spec.html and include: {phrase}")

    settings_path = root / ".claude/settings.json"
    if settings_path.exists():
        settings = load_json(settings_path, errors)
        if isinstance(settings, dict):
            env = settings.get("env")
            if not isinstance(env, dict) or env.get(CLAUDE_AGENT_TEAM_ENV) != "1":
                errors.append(f"Missing Claude agent team env flag: env.{CLAUDE_AGENT_TEAM_ENV} = \"1\"")
            permissions = settings.get("permissions")
            deny = permissions.get("deny") if isinstance(permissions, dict) else None
            if not isinstance(deny, list) or not deny:
                errors.append("Missing permissions.deny entries in .claude/settings.json")

    ownership_path = root / ".agent-loop/coordination/ownership.json"
    if ownership_path.exists():
        ownership = load_json(ownership_path, errors)
        if isinstance(ownership, dict):
            claims = ownership.get("claims", [])
            if not isinstance(claims, list):
                errors.append(".agent-loop/coordination/ownership.json claims must be a list")
                claims = []
            active = [claim for claim in claims if isinstance(claim, dict) and claim.get("status") == "active"]
            for index, left in enumerate(active):
                for right in active[index + 1 :]:
                    same_claimant = (
                        left.get("tool") == right.get("tool")
                        and left.get("agent") == right.get("agent")
                        and left.get("task_id") == right.get("task_id")
                    )
                    if same_claimant:
                        continue
                    if paths_overlap(str(left.get("path", "")), str(right.get("path", ""))):
                        errors.append(
                            "Active ownership conflict: "
                            f"{left.get('tool')}/{left.get('agent')} owns {left.get('path')} and "
                            f"{right.get('tool')}/{right.get('agent')} owns {right.get('path')}"
                        )
        elif ownership is not None:
            errors.append(".agent-loop/coordination/ownership.json must contain an object")

    return errors


def package_scripts(root: Path) -> Dict[str, str]:
    package_path = root / "package.json"
    if not package_path.exists():
        return {}
    try:
        data = json.loads(package_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return {"__error__": f"Invalid JSON in package.json: {exc}"}
    scripts = data.get("scripts", {})
    return scripts if isinstance(scripts, dict) else {}


def run_command(root: Path, command: List[str]) -> Optional[str]:
    printable = " ".join(command)
    print(f"running: {printable}")
    try:
        completed = subprocess.run(command, cwd=root, check=False)
    except FileNotFoundError:
        return f"Command not found: {command[0]}"
    if completed.returncode != 0:
        return f"Command failed ({completed.returncode}): {printable}"
    return None


def markdown_files(root: Path) -> List[Path]:
    files: List[Path] = []
    for path in root.rglob("*.md"):
        relative_parts = path.relative_to(root).parts
        if any(part in IGNORED_PARTS for part in relative_parts):
            continue
        files.append(path)
    return files


def scan_markdown_conflicts(root: Path) -> List[str]:
    errors: List[str] = []
    for path in markdown_files(root):
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            stripped = line.strip()
            if stripped.startswith("<<<<<<<") or stripped.startswith("=======") or stripped.startswith(">>>>>>>"):
                errors.append(f"Merge conflict marker in {path.relative_to(root).as_posix()}:{line_number}")
    return errors


def verify_project(root: Path) -> List[str]:
    errors: List[str] = []
    scripts = package_scripts(root)
    if "__error__" in scripts:
        errors.append(scripts["__error__"])
    else:
        for script_name in ["lint", "typecheck", "test", "build"]:
            if script_name in scripts:
                npm_command = ["npm", "test"] if script_name == "test" else ["npm", "run", script_name]
                error = run_command(root, npm_command)
                if error:
                    errors.append(error)

    if (root / "tests").is_dir() or (root / "pyproject.toml").exists():
        python = os.environ.get("PYTHON") or sys.executable
        if (root / "tests").is_dir():
            error = run_command(root, [python, "-m", "unittest", "discover", "-s", "tests", "-p", "test_*.py"])
            if error:
                errors.append(error)

    errors.extend(scan_markdown_conflicts(root))
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify this project and its compound orchestration harness.")
    parser.add_argument("--compound-only", action="store_true", help="Check only Compound Orchestrator files and claims.")
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    errors = verify_compound(root)
    if not args.compound_only and not errors:
        errors.extend(verify_project(root))

    if errors:
        print("verification: FAIL")
        for error in errors:
            print(f"  - {error}")
        return 1

    print("verification: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
"""


def verify_sh_template() -> str:
    return r"""
#!/usr/bin/env sh
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
PYTHON=${PYTHON:-python3}

cd "$ROOT"
"$PYTHON" scripts/verify.py "$@"
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
    if ($env:PYTHON) {
        $Python = $env:PYTHON
    }
    elseif (Get-Command python -ErrorAction SilentlyContinue) {
        $Python = "python"
    }
    else {
        $Python = "python3"
    }

    $VerifyArgs = @("scripts/verify.py")
    if ($CompoundOnly) {
        $VerifyArgs += "--compound-only"
    }

    & $Python @VerifyArgs
    if ($LASTEXITCODE -ne 0) {
        throw "scripts/verify.py failed with exit code $LASTEXITCODE"
    }
}
finally {
    Pop-Location
}
"""


def claude_command_templates() -> Dict[str, str]:
    return {
        ".claude/commands/compound-init.md": """
# Compound Init

Initialize this repository for compound engineering.

Run:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/compound_orchestrator.py" init --target .
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/compound_orchestrator.py" check --target .
```

Confirm that `.claude/settings.json` enables Claude Code agent teams with `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`, and use `.agent-loop/codex-parallel-contract.md` for the matching Codex or other-agent parallel workflow.
Also review `.agent-loop/harness-checklist.md`, `.agent-loop/readme-maintenance.md`, and `CODEBASE_MAP.md` so the project is navigable before adding MCP or LSP complexity.
The initialized project should be portable through `scripts/compound_orchestrator.py`, `scripts/verify.py`, `scripts/verify.ps1`, and `scripts/verify.sh`.
""",
        ".claude/commands/compound-start.md": """
# Compound Start

Create or update a task brief before implementation starts.

Steps:

1. Restate the goal and definition of done.
2. Inspect `STRATEGY.md`, `README.md`, `AGENTS.md`, `CLAUDE.md`, and relevant `docs/patterns`, `docs/decisions`, and `docs/failures`.
3. Create a plan in `docs/plans/` using `.agent-loop/task-brief-template.md`.
4. Identify parallel agent lanes only when they are independent.
5. Stop before implementation if ownership, verification, or README impact is unclear.
""",
        ".claude/commands/compound-plan.md": """
# Compound Plan

Turn the current task brief into an implementation plan.

Include:

- the six core planning artifacts: `prd.html`, `planning.html`, `spec.html`, `test-cases.html`, `architecture.html`, and `users.html`
- files, drafts, or artifacts likely to change
- tests to add or run
- README sections likely to change or a note that README is unaffected
- risks and mitigations
- agent lanes with disjoint ownership
- completion gate checklist

Use dependency-aware planning: parallelize PRD, users, architecture, planning, and test-risk drafting; serialize integration, `spec.html`, `test-cases.html`, and acceptance.
""",
        ".claude/commands/compound-review.md": """
# Compound Review

Review the current diff using `.agent-loop/review-rubric.md`.

Lead with findings. Include file and line references when possible. Call out missing verification, stale README content, and any lesson that should become a durable compound note.
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
Update `README.md` whenever setup, usage, workflow, architecture, outputs, manuscript structure, export process, or reader-facing behavior changed.
""",
        ".claude/commands/compound-team-start.md": """
# Compound Team Start

Create a Claude Code agent team for work that benefits from inter-agent coordination.

Prerequisites:

- `.claude/settings.json` contains `env.CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS` set to `"1"`.
- `.agent-loop/team-topology.md` defines roles, scopes, and completion gates.
- The task has separable lanes and disjoint write ownership.

Steps:

1. Create or update a plan with `compound-start`.
2. Create a team run note in `docs/compound/`.
3. Ask Claude to create a dependency-aware planning team.
4. Parallelize PRD, users, architecture, planning, and early test strategy.
5. Serialize integration, `spec.html`, `test-cases.html`, and final acceptance.
6. Run the two-round cross-review protocol before implementation.
7. Assign each teammate a scoped task, owned files, output artifact, and verification responsibility.
8. Wait for teammates to finish before synthesis.
9. Write a compound note before declaring completion.

Starter prompt:

```text
Create an agent team for this task. Use `.agent-loop/team-topology.md`, `.agent-loop/core-planning-artifacts.md`, and `.agent-loop/parallel-agent-team-protocol.md`.
Spawn PRD, users/workflow, architecture, planning, test-strategy, spec, test-case, and reviewer lanes as dependency order allows.
Do not start implementation until `prd.html`, `planning.html`, `spec.html`, `test-cases.html`, `architecture.html`, and `users.html` pass two review rounds and final acceptance.
Keep write scopes disjoint, wait for teammates to finish, synthesize findings, run verification, and write a compound note.
```
""",
        ".claude/commands/compound-harness-check.md": """
# Compound Harness Check

Audit this repository's cross-agent project harness.

Run:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/compound_orchestrator.py" harness-check --target .
```

Summarize missing setup in priority order: navigation, README maintenance, layered `CLAUDE.md`, permissions deny rules, cross-platform verification, hooks, path-scoped skills, LSP/MCP roadmap, ownership, and review cadence.
""",
        ".claude/commands/compound-claim.md": """
# Compound Claim

Claim files, directories, drafts, or artifacts before editing so agent runtimes do not collide.

Run:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/compound_orchestrator.py" claim --target . --tool claude --agent "$USER" --task-id TASK_ID --paths path/to/file.py --intent "Describe planned edit"
```

If the claim fails, stop and report the existing owner. Do not edit overlapping files until the lead narrows scope or releases the claim.
""",
        ".claude/commands/compound-release.md": """
# Compound Release

Release ownership claims after a patch is integrated, abandoned, or handed off.

Run:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/compound_orchestrator.py" release --target . --tool claude --agent "$USER" --task-id TASK_ID
```
""",
        ".claude/commands/compound-ownership-status.md": """
# Compound Ownership Status

Show active Claude/Codex ownership claims.

Run:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/compound_orchestrator.py" ownership-status --target .
```
""",
        ".claude/commands/compound-cross-review.md": """
# Compound Cross Review

Use this for the required two-round cross-tool review protocol.

Steps:

1. Inspect active ownership with `compound-ownership-status`.
2. Review only the authoring agent's diff or paths named by the lead.
3. Cover all six planning artifacts when this is a planning gate: `prd.html`, `planning.html`, `spec.html`, `test-cases.html`, `architecture.html`, and `users.html`.
4. Lead with findings ordered by severity.
5. Write each stage:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/compound_orchestrator.py" cross-review --target . --task-id TASK_ID --reviewer-tool codex --author-tool claude --stage round-1-review --summary "Round 1 findings..."
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/compound_orchestrator.py" cross-review --target . --task-id TASK_ID --reviewer-tool claude --author-tool codex --stage round-1-response --summary "Claude addressed round 1..."
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/compound_orchestrator.py" cross-review --target . --task-id TASK_ID --reviewer-tool codex --author-tool claude --stage round-2-review --summary "Round 2 findings..."
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/compound_orchestrator.py" cross-review --target . --task-id TASK_ID --reviewer-tool claude --author-tool codex --stage round-2-response --summary "Claude addressed round 2..."
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/compound_orchestrator.py" cross-review --target . --task-id TASK_ID --reviewer-tool codex --author-tool claude --stage final-acceptance --summary "Accepted after two rounds."
```

Stop after two rounds unless the user explicitly asks for another loop.
""",
        ".claude/commands/compound-deliverables-check.md": """
# Compound Deliverables Check

Check that the planning contracts, two-round review artifacts, verification evidence, README freshness, and compound learning are ready for handoff.

Run:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/compound_orchestrator.py" check --target . --task-id TASK_ID
```

If this fails, address missing artifacts instead of declaring the work complete.
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

Prefer the generated cross-platform entrypoints when available: `python scripts/verify.py`, `sh scripts/verify.sh`, or `pwsh ./scripts/verify.ps1`.
""",
        ".claude/agents/compound-cross-tool-reviewer.md": """
---
name: compound-cross-tool-reviewer
description: Reviews Codex-authored or other-agent-authored changes from the Claude Code side and checks for ownership conflicts.
tools: Read, Grep, Glob, Bash
---

You are the Claude-side cross-tool reviewer. Review work written by Codex or another agent runtime.

Required checks:

- Inspect `.agent-loop/coordination/ownership.json` for overlapping active claims.
- Confirm the authoring agent edited only claimed files.
- Review correctness, tests, security, maintainability, factual drift, README freshness, and writing clarity when relevant.
- Do not edit files unless the lead explicitly assigns a patch and ownership has been claimed.
- Write or request a cross-review artifact in `docs/cross-reviews/`.

Lead with findings. If no findings, say that clearly and list residual risk.
""",
    }


def init_project(root: Path, *, force: bool = False) -> WriteReport:
    root = root.resolve()
    report = ensure_dirs(root)

    report.extend(upsert_readme(root))
    report.extend(upsert_managed_block(root, "AGENTS.md", "Agent Instructions", common_protocol_block("Codex")))
    report.extend(upsert_managed_block(root, "CLAUDE.md", "Claude Instructions", common_protocol_block("Claude Code")))
    report.extend(merge_claude_settings(root))

    for relative, content in {
        "CODEBASE_MAP.md": codebase_map_template(),
        "STRATEGY.md": strategy_template(),
        ".agent-loop/readme-maintenance.md": readme_maintenance_template(),
        ".agent-loop/task-brief-template.md": task_brief_template(),
        ".agent-loop/handoff-template.md": handoff_template(),
        ".agent-loop/review-rubric.md": review_rubric_template(),
        ".agent-loop/eval-scorecard.md": scorecard_template(),
        ".agent-loop/harness-checklist.md": harness_checklist_template(),
        ".agent-loop/module-claude-template.md": module_claude_template(),
        ".agent-loop/path-scoped-skill-template.md": path_scoped_skill_template(),
        ".agent-loop/lsp-mcp-roadmap.md": lsp_mcp_roadmap_template(),
        ".agent-loop/harness-ownership.md": ownership_template(),
        ".agent-loop/team-topology.md": team_topology_template(),
        ".agent-loop/codex-parallel-contract.md": codex_parallel_contract_template(),
        ".agent-loop/cross-tool-protocol.md": cross_tool_protocol_template(),
        ".agent-loop/core-planning-artifacts.md": core_planning_artifacts_template(),
        ".agent-loop/two-round-review-protocol.md": two_round_review_protocol_template(),
        ".agent-loop/parallel-agent-team-protocol.md": parallel_agent_team_protocol_template(),
        ".agent-loop/deliverables-checklist.md": deliverables_checklist_template(),
        "prd.html": planning_html_template("prd.html"),
        "planning.html": planning_html_template("planning.html"),
        "spec.html": planning_html_template("spec.html"),
        "test-cases.html": planning_html_template("test-cases.html"),
        "architecture.html": planning_html_template("architecture.html"),
        "architecture.excalidraw": architecture_excalidraw_template(),
        "users.html": planning_html_template("users.html"),
        "scripts/verify.py": verify_py_template(),
        "scripts/verify.ps1": verify_script_template(),
        "scripts/verify.sh": verify_sh_template(),
        **claude_command_templates(),
        **claude_agent_templates(),
    }.items():
        report.extend(write_file(root, relative, content, force=force))
    report.extend(copy_orchestrator_script(root, force=force))
    verify_sh = root / "scripts/verify.sh"
    if verify_sh.exists():
        verify_sh.chmod(verify_sh.stat().st_mode | 0o111)
    report.extend(save_ownership(root, load_ownership(root)))

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
- [ ] Complete six planning contracts (`prd.html`, `planning.html`, `spec.html`, `test-cases.html`, `architecture.html`, `users.html`)
- [ ] Run two-round cross review for planning artifacts before implementation
- [ ] Implement scoped change
- [ ] Add or update verification
- [ ] Run two-round cross review for implementation artifacts
- [ ] Update README if project setup, usage, workflow, architecture, outputs, or audience-facing behavior changed
- [ ] Write compound note

## Core Planning Contracts

| Artifact | Owner | Status |
| --- | --- | --- |
| `prd.html` | PRD agent | Pending |
| `planning.html` | Planning agent | Pending |
| `spec.html` | Spec agent | Pending |
| `test-cases.html` | Test-case agent | Pending |
| `architecture.html` + `architecture.excalidraw` | Architecture agent | Pending |
| `users.html` | Users/workflow agent | Pending |

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


def team_run_content(task_id: str, title: str, mode: str) -> str:
    return f"""
# Team Run: {title}

Task id: `{task_id}`
Mode: `{mode}`

## Shared Contract

- `.agent-loop/team-topology.md`
- `.agent-loop/codex-parallel-contract.md`
- `.agent-loop/core-planning-artifacts.md`
- `.agent-loop/parallel-agent-team-protocol.md`
- `.agent-loop/two-round-review-protocol.md`
- `.agent-loop/review-rubric.md`

## Team Members

| Agent | Runtime | Role | Owned Files Or Scope | Output Artifact | Status |
| --- | --- | --- | --- | --- | --- |
| Lead Integrator | {mode} | Synthesis and integration | TBD | Final diff and summary | Pending |
| PRD Agent | {mode} | Requirements contract | `prd.html` | PRD draft | Pending |
| Users Agent | {mode} | User/workflow contract | `users.html` | User workflow draft | Pending |
| Architecture Agent | {mode} | Architecture contract and diagram | `architecture.html`, `architecture.excalidraw` | Architecture draft | Pending |
| Planning Agent | {mode} | Delivery plan | `planning.html` | Planning draft | Pending |
| Spec Agent | {mode} | Behavioral contract after integration | `spec.html` | Spec draft | Pending |
| Test Runner | {mode} | Test cases from spec | `test-cases.html` | Test matrix | Pending |
| Reviewer | {mode} | Findings and learning | Read-only | Review findings | Pending |

## Coordination Notes

- Keep write ownership disjoint.
- Before edits, every worker claims files with `compound_orchestrator.py claim`.
- A failed claim means the worker must stop instead of editing.
- Claude Code reviews Codex-authored changes with `compound-cross-tool-reviewer`.
- Codex reviews Claude-authored changes with `codex-cross-tool-reviewer`.
- Teammates should share findings before implementation when coordination is needed.
- The lead waits for teammates before final synthesis.
- Parallelize PRD, users, architecture, planning, and early test strategy; serialize integration, spec, test-case finalization, and acceptance.
- Run exactly two cross-review rounds unless the user explicitly asks for more.
- The lead keeps `README.md` current when the work changes setup, usage, workflow, architecture, outputs, or reader-facing behavior.

## Verification

- Command:
- Result:

## Ownership

- Status command: `python scripts/compound_orchestrator.py ownership-status --target .`
- Conflict resolution:

## Review Findings

## Cross-Tool Review

## Compound Learning
"""


def start_team(
    root: Path,
    title: str,
    *,
    mode: str = "claude-agent-team",
    today: Optional[_dt.date] = None,
    force: bool = False,
) -> Tuple[str, WriteReport]:
    root = root.resolve()
    report = init_project(root, force=force)
    task_id, task_report = start_task(root, title, today=today, force=force)
    report.extend(task_report)
    report.extend(write_file(root, f"docs/compound/{task_id}-team-run.md", team_run_content(task_id, title, mode), force=force))
    return task_id, report


def note_content(kind: str, title: str, summary: str, task_id: Optional[str]) -> str:
    date = _dt.date.today().isoformat()
    task_line = f"Task id: `{task_id}`\n" if task_id else ""
    prompts = {
        "pattern": "## Reuse Rule\n\nWhen this situation appears again, future agents should:\n",
        "decision": "## Decision\n\n## Alternatives Rejected\n\n## Consequences\n",
        "failure": "## Root Cause\n\n## Fix\n\n## Prevention Rule\n",
        "review": "## Findings\n\n## Verification\n\n## Follow-Up\n",
        "cross-review": "## Cross-Tool Findings\n\n## Ownership Check\n\n## Verification\n\n## Follow-Up\n",
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


def cross_review(
    root: Path,
    *,
    task_id: str,
    reviewer_tool: str,
    author_tool: str,
    summary: str,
    stage: str = "round-1-review",
    force: bool = False,
) -> Tuple[str, WriteReport]:
    reviewer_tool = validate_tool_name(reviewer_tool, field="reviewer_tool")
    author_tool = validate_tool_name(author_tool, field="author_tool")
    if reviewer_tool == author_tool:
        raise ValueError("cross-tool review requires different reviewer and author tools")
    if stage not in CROSS_REVIEW_STAGES:
        raise ValueError(f"stage must be one of: {', '.join(CROSS_REVIEW_STAGES)}")

    root = root.resolve()
    claims = active_claims(root)
    relevant_claims = [
        claim
        for claim in claims
        if claim.get("task_id") == task_id and claim.get("tool") == author_tool
    ]
    claim_lines = "\n".join(
        f"- `{claim.get('path')}` claimed by {claim.get('tool')}/{claim.get('agent')}: {claim.get('intent', '')}"
        for claim in relevant_claims
    ) or "- No active author-tool claims found for this task; reviewer should confirm this is expected."
    title = f"{stage.replace('-', ' ').title()}: {reviewer_tool.title()} And {author_tool.title()} Cross Review"
    artifact_lines = "\n".join(f"- `{name}`" for name in CORE_PLANNING_ARTIFACTS)
    if stage.endswith("response"):
        stage_prompt = """
## Response To Findings

- Accepted comments:
- Changes made:
- Comments declined with rationale:

## Verification Run

- Command:
- Result:
"""
    elif stage == "final-acceptance":
        stage_prompt = """
## Final Acceptance

- Planning contracts accepted:
- Implementation or document changes accepted:
- Residual risks:
- User-requested third round needed: no
"""
    else:
        stage_prompt = """
## Findings

Lead with blocking findings, then important should-fix items, then residual risks.

## Verification

- Command:
- Result:

## Follow-Up Required From Author
"""
    body = f"""
# {title}

Task id: `{task_id}`
Reviewer tool: `{reviewer_tool}`
Author tool: `{author_tool}`
Stage: `{stage}`
Date: `{_dt.date.today().isoformat()}`

## Summary

{summary}

## Planning Artifacts Covered

{artifact_lines}

## Author Claims Checked

{claim_lines}

{stage_prompt}
"""
    relative = f"docs/cross-reviews/{task_id}/{stage}.md"
    report = ensure_dirs(root)
    report.extend(write_file(root, relative, body, force=force))
    return relative, report


def check_project(root: Path, task_id: Optional[str] = None) -> Tuple[bool, List[str]]:
    root = root.resolve()
    failures: List[str] = []

    for item in REQUIRED_DIRS:
        if not (root / item).is_dir():
            failures.append(f"Missing directory: {item}")

    required_files = [
        "README.md",
        "AGENTS.md",
        "CLAUDE.md",
        "CODEBASE_MAP.md",
        "STRATEGY.md",
        ".agent-loop/readme-maintenance.md",
        ".agent-loop/task-brief-template.md",
        ".agent-loop/handoff-template.md",
        ".agent-loop/review-rubric.md",
        ".agent-loop/eval-scorecard.md",
        ".agent-loop/harness-checklist.md",
        ".agent-loop/module-claude-template.md",
        ".agent-loop/path-scoped-skill-template.md",
        ".agent-loop/lsp-mcp-roadmap.md",
        ".agent-loop/harness-ownership.md",
        ".agent-loop/team-topology.md",
        ".agent-loop/codex-parallel-contract.md",
        ".agent-loop/cross-tool-protocol.md",
        ".agent-loop/core-planning-artifacts.md",
        ".agent-loop/two-round-review-protocol.md",
        ".agent-loop/parallel-agent-team-protocol.md",
        ".agent-loop/deliverables-checklist.md",
        ".agent-loop/coordination/ownership.json",
        "prd.html",
        "planning.html",
        "spec.html",
        "test-cases.html",
        "architecture.html",
        "architecture.excalidraw",
        "users.html",
        ".claude/settings.json",
        "scripts/compound_orchestrator.py",
        "scripts/verify.py",
        "scripts/verify.ps1",
        "scripts/verify.sh",
        ".claude/commands/compound-start.md",
        ".claude/commands/compound-plan.md",
        ".claude/commands/compound-review.md",
        ".claude/commands/compound-learn.md",
        ".claude/commands/compound-init.md",
        ".claude/commands/compound-team-start.md",
        ".claude/commands/compound-harness-check.md",
        ".claude/commands/compound-claim.md",
        ".claude/commands/compound-release.md",
        ".claude/commands/compound-ownership-status.md",
        ".claude/commands/compound-cross-review.md",
        ".claude/commands/compound-deliverables-check.md",
        ".claude/agents/compound-architect.md",
        ".claude/agents/compound-reviewer.md",
        ".claude/agents/compound-test-runner.md",
        ".claude/agents/compound-cross-tool-reviewer.md",
    ]
    for item in required_files:
        if not (root / item).is_file():
            failures.append(f"Missing file: {item}")

    architecture_html = root / "architecture.html"
    if architecture_html.exists():
        text = architecture_html.read_text(encoding="utf-8").lower()
        if "excalidraw" not in text or "architecture.excalidraw" not in text:
            failures.append("architecture.html must reference an Excalidraw-compatible diagram, usually architecture.excalidraw")
    architecture_diagram = root / "architecture.excalidraw"
    if architecture_diagram.exists():
        try:
            diagram = json.loads(architecture_diagram.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            failures.append(f"Invalid JSON in architecture.excalidraw: {exc}")
        else:
            if not isinstance(diagram, dict) or diagram.get("type") != "excalidraw":
                failures.append("architecture.excalidraw must be an Excalidraw-compatible JSON file")
    test_cases = root / "test-cases.html"
    if test_cases.exists():
        text = test_cases.read_text(encoding="utf-8").lower()
        for phrase in ["spec.html", "happy", "edge", "error", "performance", "user workflow", "acceptance"]:
            if phrase not in text:
                failures.append(f"test-cases.html must map coverage to spec.html and include: {phrase}")

    for item in ["README.md", "AGENTS.md", "CLAUDE.md"]:
        path = root / item
        if path.exists():
            text = path.read_text(encoding="utf-8")
            if MANAGED_START not in text or MANAGED_END not in text:
                failures.append(f"Missing managed compound block in {item}")

    readme_policy = root / ".agent-loop/readme-maintenance.md"
    if readme_policy.exists():
        text = readme_policy.read_text(encoding="utf-8")
        for phrase in ["Remove old information", "Keep unchanged information", "Add new content", "Reorganize"]:
            if phrase not in text:
                failures.append(f"README maintenance guide is missing policy phrase: {phrase}")

    settings = root / ".claude/settings.json"
    if settings.exists():
        try:
            settings_data = json.loads(settings.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            failures.append(f"Invalid JSON in .claude/settings.json: {exc}")
        else:
            env = settings_data.get("env")
            if not isinstance(env, dict) or env.get(CLAUDE_AGENT_TEAM_ENV) != "1":
                failures.append(f"Missing Claude agent team env flag: env.{CLAUDE_AGENT_TEAM_ENV} = \"1\"")
            permissions = settings_data.get("permissions")
            deny = permissions.get("deny") if isinstance(permissions, dict) else None
            if not isinstance(deny, list):
                failures.append("Missing permissions.deny list in .claude/settings.json")
            else:
                missing_denies = [item for item in DEFAULT_PERMISSION_DENY if item not in deny]
                if missing_denies:
                    failures.append(f"Missing default permissions.deny entries: {', '.join(missing_denies)}")
    ownership = root / OWNERSHIP_FILE
    if ownership.exists():
        try:
            load_ownership(root)
        except ValueError as exc:
            failures.append(str(exc))
        else:
            for conflict in active_ownership_conflicts(root):
                failures.append(
                    "Active ownership conflict: "
                    f"{conflict['left_tool']}/{conflict['left_agent']} owns {conflict['left_path']} and "
                    f"{conflict['right_tool']}/{conflict['right_agent']} owns {conflict['right_path']}"
                )

    if task_id:
        task_files = [
            f"docs/plans/{task_id}.md",
            f"docs/reviews/{task_id}.md",
            f"docs/compound/{task_id}.md",
        ]
        task_files.extend(f"docs/cross-reviews/{task_id}/{stage}.md" for stage in CROSS_REVIEW_STAGES)
        for item in task_files:
            if not (root / item).is_file():
                failures.append(f"Task gate missing file: {item}")
        for stage in CROSS_REVIEW_STAGES:
            path = root / f"docs/cross-reviews/{task_id}/{stage}.md"
            if path.exists():
                text = path.read_text(encoding="utf-8")
                for artifact in CORE_PLANNING_ARTIFACTS:
                    if artifact not in text:
                        failures.append(f"Task gate review file {path.relative_to(root).as_posix()} must mention {artifact}")

    return not failures, failures


def harness_audit(root: Path) -> Tuple[bool, List[str], List[str]]:
    root = root.resolve()
    warnings: List[str] = []
    failures: List[str] = []

    ok, structural_failures = check_project(root)
    failures.extend(structural_failures)

    claude = root / "CLAUDE.md"
    if claude.exists():
        line_count = len(claude.read_text(encoding="utf-8").splitlines())
        if line_count > 160:
            warnings.append(f"Root CLAUDE.md is {line_count} lines; keep root context lean and move local details deeper.")
    else:
        failures.append("Missing root CLAUDE.md")

    subdirectory_claudes = [
        path
        for path in root.rglob("CLAUDE.md")
        if path != claude and ".git" not in path.parts and "node_modules" not in path.parts
    ]
    if not subdirectory_claudes:
        warnings.append("No subdirectory CLAUDE.md files found; add them for services/modules with local commands.")

    skill_dirs = list((root / ".claude/skills").glob("*/SKILL.md")) if (root / ".claude/skills").exists() else []
    nested_skill_dirs = [
        path
        for path in root.rglob(".claude/skills/*/SKILL.md")
        if ".git" not in path.parts and path not in skill_dirs
    ]
    if not skill_dirs and not nested_skill_dirs:
        warnings.append("No project or path-scoped skills found yet; promote repeated task-specific expertise into skills.")

    ownership = root / ".agent-loop/harness-ownership.md"
    if ownership.exists():
        text = ownership.read_text(encoding="utf-8")
        if "- Name:" in text and "- Next review:" in text:
            warnings.append("Harness ownership template still needs a named DRI and review cadence.")

    return not failures, failures, warnings


def hook_context(stdin_text: str) -> str:
    try:
        payload = json.loads(stdin_text) if stdin_text.strip() else {}
    except json.JSONDecodeError:
        payload = {}
    cwd = Path(payload.get("cwd") or ".").resolve()
    root = cwd
    for candidate in [cwd, *cwd.parents]:
        if (candidate / ".agent-loop").exists() or (candidate / ".git").exists():
            root = candidate
            break

    reminders = [
        "Compound Orchestrator harness reminder:",
        "- Start Claude Code in the most specific subdirectory for the work; parent CLAUDE.md files still load.",
        "- Keep root CLAUDE.md lean; put local commands and conventions in subdirectory CLAUDE.md files.",
        "- Use hooks for automatic behavior and path-scoped skills for specialized expertise.",
        "- Add MCP/LSP only after navigation, permissions, hooks, and ownership are healthy.",
        "- Before editing in mixed Claude/Codex work, claim files in .agent-loop/coordination/ownership.json.",
        "- Keep README.md current when setup, usage, architecture, workflow, outputs, or reader-facing behavior changes.",
    ]
    if (root / "CODEBASE_MAP.md").exists():
        reminders.append("- Navigation map available: CODEBASE_MAP.md")
    if (root / ".agent-loop/harness-checklist.md").exists():
        reminders.append("- Harness checklist available: .agent-loop/harness-checklist.md")
    if (root / ".agent-loop/lsp-mcp-roadmap.md").exists():
        reminders.append("- LSP/MCP roadmap available: .agent-loop/lsp-mcp-roadmap.md")
    if (root / ".agent-loop/readme-maintenance.md").exists():
        reminders.append("- README maintenance guide available: .agent-loop/readme-maintenance.md")
    return "\n".join(reminders)


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
        hooks_path = claude_data.get("hooks")
        if hooks_path and not (plugin_root / str(hooks_path).replace("./", "")).exists():
            failures.append(f"Claude hooks path does not exist: {hooks_path}")

    for required in [
        "README.md",
        "LICENSE",
        "skills/compound-orchestrator/SKILL.md",
        "hooks/hooks.json",
        "scripts/verify_plugin.ps1",
        "scripts/verify_plugin.sh",
        "commands/compound-init.md",
        "commands/compound-start.md",
        "commands/compound-plan.md",
        "commands/compound-review.md",
        "commands/compound-learn.md",
        "commands/compound-team-start.md",
        "commands/compound-harness-check.md",
        "commands/compound-claim.md",
        "commands/compound-release.md",
        "commands/compound-ownership-status.md",
        "commands/compound-cross-review.md",
        "commands/compound-deliverables-check.md",
        "agents/compound-architect.agent.md",
        "agents/compound-reviewer.agent.md",
        "agents/compound-test-runner.agent.md",
        "agents/compound-cross-tool-reviewer.agent.md",
        "skills/codex-cross-tool-reviewer/SKILL.md",
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
        verifier = subprocess.run(
            [sys.executable, str(target / "scripts/verify.py"), "--compound-only"],
            cwd=target,
            text=True,
            capture_output=True,
            check=False,
        )
        if verifier.returncode != 0:
            failures.append(f"generated verifier failed: {verifier.stdout}{verifier.stderr}")
        audit_ok, audit_failures, _audit_warnings = harness_audit(target)
        if not audit_ok:
            failures.extend(f"harness audit: {item}" for item in audit_failures)
        team_task_id, _ = start_team(
            target,
            "Exercise team orchestration",
            mode="codex-parallel-agents",
            today=_dt.date(2026, 5, 21),
        )
        if not (target / f"docs/compound/{team_task_id}-team-run.md").exists():
            failures.append("team-start did not create a team run artifact")
        try:
            claim_scope(
                target,
                tool="claude",
                agent="claude-implementer",
                task_id=team_task_id,
                paths=["src/demo.py"],
                intent="Dummy Claude edit",
            )
            claim_scope(
                target,
                tool="codex",
                agent="codex-worker",
                task_id=team_task_id,
                paths=["src/demo.py"],
                intent="Dummy Codex edit",
            )
            failures.append("overlapping Claude/Codex claims were not rejected")
        except OwnershipConflict:
            pass
        cross_review_path, _ = cross_review(
            target,
            task_id=team_task_id,
            reviewer_tool="codex",
            author_tool="claude",
            summary="Dummy cross-tool review completed.",
        )
        if not (target / cross_review_path).exists():
            failures.append("cross-review did not create a review artifact")
        release_scope(target, tool="claude", agent="claude-implementer", task_id=team_task_id)
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
        for stage in CROSS_REVIEW_STAGES:
            cross_review(
                target,
                task_id=task_id,
                reviewer_tool="codex" if "review" in stage or stage == "final-acceptance" else "claude",
                author_tool="claude" if "review" in stage or stage == "final-acceptance" else "codex",
                summary=f"Self-test {stage} covers all six planning artifacts.",
                stage=stage,
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

    audit_p = sub.add_parser("harness-check", help="Audit cross-agent project harness readiness.")
    audit_p.add_argument("--target", default=".", help="Project root to audit.")
    audit_p.add_argument("--json", action="store_true", help="Print JSON report.")

    hook_p = sub.add_parser("hook-context", help="Emit concise SessionStart context for Claude Code hooks.")

    start_p = sub.add_parser("start", help="Create brainstorm and plan artifacts for a task.")
    start_p.add_argument("--target", default=".", help="Project root.")
    start_p.add_argument("--title", required=True, help="Task title.")
    start_p.add_argument("--force", action="store_true", help="Overwrite existing generated task files.")
    start_p.add_argument("--json", action="store_true", help="Print JSON report.")

    team_p = sub.add_parser("team-start", help="Create task artifacts for a Claude or Codex multi-agent run.")
    team_p.add_argument("--target", default=".", help="Project root.")
    team_p.add_argument("--title", required=True, help="Task title.")
    team_p.add_argument(
        "--mode",
        default="claude-agent-team",
        choices=["claude-agent-team", "codex-parallel-agents"],
        help="Runtime mode for the team run artifact.",
    )
    team_p.add_argument("--force", action="store_true", help="Overwrite existing generated team files.")
    team_p.add_argument("--json", action="store_true", help="Print JSON report.")

    claim_p = sub.add_parser("claim", help="Claim file ownership before Claude/Codex edits.")
    claim_p.add_argument("--target", default=".", help="Project root.")
    claim_p.add_argument(
        "--tool",
        required=True,
        help=f"Agent runtime claiming ownership, for example: {', '.join(SUGGESTED_TOOL_NAMES)}.",
    )
    claim_p.add_argument("--agent", required=True, help="Agent or teammate name.")
    claim_p.add_argument("--task-id", required=True, help="Task id.")
    claim_p.add_argument("--paths", nargs="+", required=True, help="Files, directories, or globs to claim.")
    claim_p.add_argument("--intent", default="", help="Planned edit summary.")
    claim_p.add_argument("--force", action="store_true", help="Record claim despite conflicts.")
    claim_p.add_argument("--json", action="store_true", help="Print JSON report.")

    release_p = sub.add_parser("release", help="Release file ownership claims.")
    release_p.add_argument("--target", default=".", help="Project root.")
    release_p.add_argument("--tool", help=f"Agent runtime to release, for example: {', '.join(SUGGESTED_TOOL_NAMES)}.")
    release_p.add_argument("--agent", help="Agent or teammate name to release.")
    release_p.add_argument("--task-id", help="Task id to release.")
    release_p.add_argument("--paths", nargs="+", help="Specific paths to release.")
    release_p.add_argument("--json", action="store_true", help="Print JSON report.")

    status_p = sub.add_parser("ownership-status", help="Show active file ownership claims.")
    status_p.add_argument("--target", default=".", help="Project root.")
    status_p.add_argument("--json", action="store_true", help="Print JSON report.")

    cross_p = sub.add_parser("cross-review", help="Record a Claude/Codex cross-tool review artifact.")
    cross_p.add_argument("--target", default=".", help="Project root.")
    cross_p.add_argument("--task-id", required=True, help="Task id.")
    cross_p.add_argument("--reviewer-tool", required=True, help="Agent runtime doing the review.")
    cross_p.add_argument("--author-tool", required=True, help="Agent runtime whose work is being reviewed.")
    cross_p.add_argument("--summary", required=True, help="Review summary.")
    cross_p.add_argument(
        "--stage",
        default="round-1-review",
        choices=CROSS_REVIEW_STAGES,
        help="Two-round review stage to record.",
    )
    cross_p.add_argument("--force", action="store_true", help="Overwrite existing review artifact.")
    cross_p.add_argument("--json", action="store_true", help="Print JSON report.")

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

    if args.command == "harness-check":
        ok, failures, warnings = harness_audit(Path(args.target))
        if args.json:
            print(json.dumps({"ok": ok, "failures": failures, "warnings": warnings}, indent=2, sort_keys=True))
        else:
            print("harness audit: PASS" if ok else "harness audit: FAIL")
            for failure in failures:
                print(f"  - {failure}")
            if warnings:
                print("warnings:")
                for warning in warnings:
                    print(f"  - {warning}")
        return 0 if ok else 1

    if args.command == "hook-context":
        print(hook_context(sys.stdin.read()))
        return 0

    if args.command == "start":
        task_id, report = start_task(Path(args.target), args.title, force=args.force)
        print_report(report, json_output=args.json, extra={"task_id": task_id})
        return 0

    if args.command == "team-start":
        task_id, report = start_team(Path(args.target), args.title, mode=args.mode, force=args.force)
        print_report(report, json_output=args.json, extra={"task_id": task_id, "mode": args.mode})
        return 0

    if args.command == "claim":
        try:
            report = claim_scope(
                Path(args.target),
                tool=args.tool,
                agent=args.agent,
                task_id=args.task_id,
                paths=args.paths,
                intent=args.intent,
                force=args.force,
            )
        except OwnershipConflict as exc:
            if args.json:
                print(json.dumps({"ok": False, "conflicts": exc.conflicts}, indent=2, sort_keys=True))
            else:
                print("ownership claim: FAIL")
                for conflict in exc.conflicts:
                    print(
                        "  - "
                        f"{conflict['requested_path']} overlaps {conflict['existing_path']} "
                        f"owned by {conflict['existing_tool']}/{conflict['existing_agent']} "
                        f"for {conflict['existing_task_id']}"
                    )
            return 1
        print_report(report, json_output=args.json, extra={"ok": "true"})
        return 0

    if args.command == "release":
        released, report = release_scope(
            Path(args.target),
            tool=args.tool,
            agent=args.agent,
            task_id=args.task_id,
            paths=args.paths,
        )
        print_report(report, json_output=args.json, extra={"released": str(released)})
        return 0

    if args.command == "ownership-status":
        claims = active_claims(Path(args.target))
        conflicts = active_ownership_conflicts(Path(args.target))
        if args.json:
            print(json.dumps({"active_claims": claims, "conflicts": conflicts}, indent=2, sort_keys=True))
        else:
            print("active ownership claims:")
            if not claims:
                print("  - none")
            for claim in claims:
                print(
                    "  - "
                    f"{claim.get('path')} owned by {claim.get('tool')}/{claim.get('agent')} "
                    f"for {claim.get('task_id')}"
                )
            if conflicts:
                print("conflicts:")
                for conflict in conflicts:
                    print(f"  - {conflict}")
        return 1 if conflicts else 0

    if args.command == "cross-review":
        note_path, report = cross_review(
            Path(args.target),
            task_id=args.task_id,
            reviewer_tool=args.reviewer_tool,
            author_tool=args.author_tool,
            summary=args.summary,
            stage=args.stage,
            force=args.force,
        )
        print_report(report, json_output=args.json, extra={"note": note_path})
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
