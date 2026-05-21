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

Bootstrap also enables Claude Code agent teams for the project by merging this into `.claude/settings.json`:

```json
{
  "env": {
    "CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS": "1"
  },
  "permissions": {
    "deny": ["Read(./.env)", "Read(./node_modules/**)", "Read(./dist/**)"]
  }
}
```

It also installs large-codebase harness templates: `CODEBASE_MAP.md`, `.agent-loop/harness-checklist.md`, `.agent-loop/module-claude-template.md`, `.agent-loop/path-scoped-skill-template.md`, `.agent-loop/lsp-mcp-roadmap.md`, and `.agent-loop/harness-ownership.md`.

It also installs cross-tool coordination files:

- `.agent-loop/coordination/ownership.json`
- `.agent-loop/cross-tool-protocol.md`
- `docs/cross-reviews/`

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

7. Audit the harness when onboarding a repo or after major workflow changes:

```powershell
& <python> <plugin-root>\scripts\compound_orchestrator.py harness-check --target <project-root>
```

8. Claim intended files before editing in mixed Claude/Codex work:

```powershell
& <python> <plugin-root>\scripts\compound_orchestrator.py claim --target <project-root> --tool codex --agent codex-worker --task-id <task-id> --paths src/file.py --intent "<planned edit>"
```

If the claim fails, stop instead of editing. Ask the lead integrator to narrow scope, release stale claims, or serialize the work.

9. Record opposite-tool review:

```powershell
& <python> <plugin-root>\scripts\compound_orchestrator.py cross-review --target <project-root> --task-id <task-id> --reviewer-tool codex --author-tool claude --summary "<findings summary>"
```

## Parallel Agent Policy

Use parallel agents for independent research, planning, test strategy, review, and competing bug hypotheses. Give every agent a role, scope, owned files, output artifact, and verification responsibility.

Avoid parallel agents for unclear ownership, same-file edits, sequential migrations, and tiny fixes. Codex must still obey the active environment's agent-spawn rules.

For multi-agent runs, use:

```powershell
& <python> <plugin-root>\scripts\compound_orchestrator.py team-start --target <project-root> --title "<task title>" --mode claude-agent-team
```

Or for Codex:

```powershell
& <python> <plugin-root>\scripts\compound_orchestrator.py team-start --target <project-root> --title "<task title>" --mode codex-parallel-agents
```

Claude Code should create an agent team only when teammate-to-teammate coordination is useful. Codex should mirror the same topology with a lead-integrator hub plus explorer, worker, test-runner, and reviewer agents, each with disjoint scopes.

Claude Code should use `compound-cross-tool-reviewer` to review Codex-authored changes. Codex should use `codex-cross-tool-reviewer` to review Claude Code-authored changes.

## Large-Codebase Harness Policy

- Root `CLAUDE.md` and `AGENTS.md` should be lean: big picture, pointers, and critical gotchas.
- Put local build, test, lint, and domain conventions in subdirectory `CLAUDE.md` files.
- Start Claude Code in the subdirectory being changed; parent context still loads.
- Generated, vendored, build, coverage, dependency, sourcemap, and secret paths should be denied in `.claude/settings.json`.
- Repeated instructions should become hooks when automatic or path-scoped skills when task-specific.
- Add LSP for typed/noisy symbol-heavy codebases before relying on broad grep.
- Add MCP only after the context layer, skills, hooks, and ownership are healthy.

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
- `.agent-loop/team-topology.md`
- `.agent-loop/codex-parallel-contract.md`
- `.agent-loop/cross-tool-protocol.md`
- `.agent-loop/harness-checklist.md`
- `.agent-loop/lsp-mcp-roadmap.md`
- `.agent-loop/harness-ownership.md`

If a lesson should affect all future work, update the managed compound block in `AGENTS.md` and `CLAUDE.md`.
