---
name: compound-orchestrator
description: Use when setting up or enforcing a compound engineering loop across Codex and Claude Code, including project memory, planning/review gates, Claude command templates, and durable learning artifacts.
---

# Compound Orchestrator

Use this skill when the user wants compound engineering to run consistently across Codex, Claude Code, or parallel agent teams.

## Operating Rule

No meaningful task starts without a task brief or plan. No meaningful task finishes without verification, review, and a compound note.

The loop is:

```text
brainstorm -> plan -> work -> review -> compound -> repeat
```

## Bootstrap

Find this plugin directory, then run:

```powershell
& <python> <plugin-root>\scripts\compound_orchestrator.py init --target <project-root>
& <python> <plugin-root>\scripts\compound_orchestrator.py check --target <project-root>
```

Use the bundled Codex Python when a system Python is not available.

## During Work

1. Start a task with a stable id:

```powershell
& <python> <plugin-root>\scripts\compound_orchestrator.py start --target <project-root> --title "<task title>"
```

2. Work from the generated plan file under `docs/plans/`.

3. Verify with the target project's `scripts/verify.ps1` when present.

4. Review the diff before declaring completion.

5. Record learning:

```powershell
& <python> <plugin-root>\scripts\compound_orchestrator.py learn --target <project-root> --kind pattern --title "<pattern>" --summary "<what future agents should reuse>"
```

6. Gate completion:

```powershell
& <python> <plugin-root>\scripts\compound_orchestrator.py check --target <project-root> --task-id <task-id>
```

## Parallel Agent Policy

Use parallel agents for independent research, planning, test strategy, review, and competing bug hypotheses. Give every agent a role, scope, owned files, output artifact, and verification responsibility.

Avoid parallel agents for unclear ownership, same-file edits, sequential migrations, and tiny fixes. Codex must still obey the active environment's agent-spawn rules.

## Claude Code Integration

The initializer writes `.claude/commands` and `.claude/agents` templates. These are intentionally plain Markdown so a project can keep them under version control and adapt them.

## Durable Memory

Prefer durable notes over chat-only conclusions:

- `docs/patterns/`
- `docs/decisions/`
- `docs/failures/`
- `docs/reviews/`
- `docs/compound/`
- `.agent-loop/eval-scorecard.md`

If a lesson should affect all future work, update the managed compound block in `AGENTS.md` and `CLAUDE.md`.
