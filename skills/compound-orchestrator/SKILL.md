---
name: compound-orchestrator
description: Use when setting up or enforcing a compound engineering loop across coding, writing, research, or documentation projects with Codex, Claude Code, and other agent runtimes.
---

# Compound Orchestrator

Use this skill when the user wants compound engineering to run consistently across Codex, Claude Code, other coding agents, writing agents, or parallel agent teams.

## Operating Rule

No meaningful task starts without a task brief or plan. No meaningful task finishes without verification, review, README freshness when relevant, and a compound note.

The loop is:

```text
brainstorm -> plan -> six planning contracts -> two-round review -> work -> two-round review -> compound -> repeat
```

Substantial projects must complete these core planning contracts before implementation:

1. `prd.html`
2. `planning.html`
3. `spec.html`
4. `test-cases.html`
5. `architecture.html` with an Excalidraw-compatible `architecture.excalidraw`
6. `users.html`

Planning is dependency-aware: parallelize PRD, users, architecture, planning, and early test strategy; then serialize integration, `spec.html`, `test-cases.html`, two-round review, and final acceptance.

## Bootstrap

Find this plugin directory, then run one of these from any platform:

```powershell
& <python> <plugin-root>\scripts\compound_orchestrator.py init --target <project-root>
& <python> <plugin-root>\scripts\compound_orchestrator.py check --target <project-root>
```

```bash
python3 <plugin-root>/scripts/compound_orchestrator.py init --target <project-root>
python3 <plugin-root>/scripts/compound_orchestrator.py check --target <project-root>
```

Use the bundled Codex Python when a system Python is not available. After bootstrap, the target project also has its own `scripts/compound_orchestrator.py`, `scripts/verify.py`, `scripts/verify.ps1`, and `scripts/verify.sh`, so other agents can use the harness without knowing the original plugin path.

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

It also installs project harness templates: `README.md` policy block, `CODEBASE_MAP.md`, `.agent-loop/readme-maintenance.md`, `.agent-loop/harness-checklist.md`, `.agent-loop/module-claude-template.md`, `.agent-loop/path-scoped-skill-template.md`, `.agent-loop/lsp-mcp-roadmap.md`, and `.agent-loop/harness-ownership.md`.

It also installs the six core planning artifacts (`prd.html`, `planning.html`, `spec.html`, `test-cases.html`, `architecture.html`, `architecture.excalidraw`, and `users.html`) plus `.agent-loop/core-planning-artifacts.md`, `.agent-loop/two-round-review-protocol.md`, `.agent-loop/parallel-agent-team-protocol.md`, and `.agent-loop/deliverables-checklist.md`.

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

3. Verify with the target project's `scripts/verify.py`, `scripts/verify.ps1`, `scripts/verify.sh`, or closest native project check.

4. Review the diff or writing artifact before declaring completion.

5. Record learning:

```powershell
& <python> <plugin-root>\scripts\compound_orchestrator.py learn --target <project-root> --kind pattern --title "<pattern>" --summary "<what future agents should reuse>"
```

6. Keep `README.md` current when setup, usage, architecture, workflow, generated outputs, public behavior, manuscript structure, export process, or review workflow changes. Remove old information, keep still-true information, add the new information, and reorganize the README so it reads cleanly.

7. Gate completion:

```powershell
& <python> <plugin-root>\scripts\compound_orchestrator.py check --target <project-root> --task-id <task-id>
```

8. Audit the harness when onboarding a repo or after major workflow changes:

```powershell
& <python> <plugin-root>\scripts\compound_orchestrator.py harness-check --target <project-root>
```

9. Claim intended files before editing in mixed-agent work:

```powershell
& <python> <plugin-root>\scripts\compound_orchestrator.py claim --target <project-root> --tool codex --agent codex-worker --task-id <task-id> --paths src/file.py --intent "<planned edit>"
```

If the claim fails, stop instead of editing. Ask the lead integrator to narrow scope, release stale claims, or serialize the work.

10. Record the two-round opposite-tool review:

```powershell
& <python> <plugin-root>\scripts\compound_orchestrator.py cross-review --target <project-root> --task-id <task-id> --reviewer-tool codex --author-tool claude --stage round-1-review --summary "<findings summary>"
& <python> <plugin-root>\scripts\compound_orchestrator.py cross-review --target <project-root> --task-id <task-id> --reviewer-tool claude --author-tool codex --stage round-1-response --summary "<revision summary>"
& <python> <plugin-root>\scripts\compound_orchestrator.py cross-review --target <project-root> --task-id <task-id> --reviewer-tool codex --author-tool claude --stage round-2-review --summary "<findings summary>"
& <python> <plugin-root>\scripts\compound_orchestrator.py cross-review --target <project-root> --task-id <task-id> --reviewer-tool claude --author-tool codex --stage round-2-response --summary "<revision summary>"
& <python> <plugin-root>\scripts\compound_orchestrator.py cross-review --target <project-root> --task-id <task-id> --reviewer-tool codex --author-tool claude --stage final-acceptance --summary "<acceptance summary>"
```

Stop after two rounds unless the user explicitly asks for another loop.

## Parallel Agent Policy

Use parallel agents for independent research, planning, test strategy, review, and competing bug hypotheses. Give every agent a role, scope, owned files, output artifact, and verification responsibility.

For planning, use dependency-aware phases:

1. Parallel draft `prd.html`, `users.html`, `architecture.html`, `planning.html`, and early test risks.
2. Lead integrator reconciles conflicts.
3. Spec agent writes `spec.html`.
4. Test-case agent writes `test-cases.html` from `spec.html`.
5. Run two cross-review rounds and record final acceptance.

Avoid parallel agents for unclear ownership, same-file edits, sequential migrations, and tiny fixes. Codex must still obey the active environment's agent-spawn rules.

For multi-agent runs, use:

```powershell
& <python> <plugin-root>\scripts\compound_orchestrator.py team-start --target <project-root> --title "<task title>" --mode claude-agent-team
```

Or for Codex:

```powershell
& <python> <plugin-root>\scripts\compound_orchestrator.py team-start --target <project-root> --title "<task title>" --mode codex-parallel-agents
```

Claude Code should create an agent team only when teammate-to-teammate coordination is useful. Codex and other runtimes should mirror the same topology with a lead-integrator hub plus explorer, worker, test-runner, and reviewer agents, each with disjoint scopes.

Claude Code should use `compound-cross-tool-reviewer` to review Codex-authored changes. Codex should use `codex-cross-tool-reviewer` to review Claude Code-authored changes.

## Large-Codebase Harness Policy

- Root `CLAUDE.md` and `AGENTS.md` should be lean: big picture, pointers, and critical gotchas.
- Put local build, test, lint, and domain conventions in subdirectory `CLAUDE.md` files.
- Start Claude Code in the subdirectory being changed; parent context still loads.
- Generated, vendored, build, coverage, dependency, sourcemap, and secret paths should be denied in `.claude/settings.json`.
- Repeated instructions should become hooks when automatic or path-scoped skills when task-specific.
- Add LSP for typed/noisy symbol-heavy codebases before relying on broad grep.
- Add MCP only after the context layer, skills, hooks, and ownership are healthy.

## Writing Project Policy

- Treat drafts, chapters, reports, source files, export scripts, and review notes as claimable artifacts.
- Review for factual drift, outline consistency, citation/source accuracy, unclear writing, and stale README instructions.
- Keep `README.md` aligned with the current manuscript or document structure, source workflow, export process, and review cadence.

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
- `.agent-loop/core-planning-artifacts.md`
- `.agent-loop/two-round-review-protocol.md`
- `.agent-loop/parallel-agent-team-protocol.md`
- `.agent-loop/deliverables-checklist.md`
- `.agent-loop/harness-checklist.md`
- `.agent-loop/lsp-mcp-roadmap.md`
- `.agent-loop/harness-ownership.md`

If a lesson should affect all future work, update the managed compound block in `AGENTS.md` and `CLAUDE.md`.

If the lesson changes setup, usage, workflow, outputs, or audience expectations, update `README.md` in the same pass.
