# Compound Orchestrator

Compound Orchestrator is a small Codex and Claude Code plugin plus project bootstrapper for running a consistent compound engineering loop across both tools.

It complements the EveryInc Compound Engineering plugin by adding project-level guardrails:

- shared Codex and Claude Code operating memory
- Claude slash-command and subagent templates
- Claude Code agent-team enablement
- a Codex parallel-agent contract that mirrors the same team topology
- large-codebase harness templates for layered `CLAUDE.md`, navigation, ownership, LSP/MCP rollout, and path-scoped skills
- Claude Code hooks for session-start context reminders and stop-time durable-learning prompts
- task brief, review, handoff, and scorecard templates
- a verification adapter
- a completion gate that checks for plan, review, and compound artifacts

## Loop

```text
brainstorm -> plan -> work -> review -> compound -> repeat
```

The important part is the final step. Every meaningful task should leave behind a reusable pattern, decision, failure note, or scorecard entry so the next task starts stronger.

## Install Into A Project

From this plugin directory:

```powershell
$py = "C:\Users\kenhu\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
& $py .\scripts\compound_orchestrator.py init --target "C:\path\to\project"
& $py .\scripts\compound_orchestrator.py check --target "C:\path\to\project"
```

The initializer is conservative. It creates missing files and directories, and it appends managed compound-engineering blocks to existing `AGENTS.md` and `CLAUDE.md` instead of replacing them.

It also merges the Claude Code agent-team flag into `.claude/settings.json`:

```json
{
  "env": {
    "CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS": "1"
  },
  "permissions": {
    "deny": [
      "Read(./.env)",
      "Read(./node_modules/**)",
      "Read(./dist/**)"
    ]
  }
}
```

The generated deny list also covers common build, coverage, generated, vendor, sourcemap, and minified JavaScript paths.

## Daily Use

Start a task:

```powershell
& $py .\scripts\compound_orchestrator.py start --target . --title "Add billing webhook retry handling"
```

Record a durable learning:

```powershell
& $py .\scripts\compound_orchestrator.py learn --target . --kind failure --title "Webhook duplicate invoice" --summary "Provider retries can arrive after our DB write succeeds. Future webhook handlers must use idempotency keys."
```

Check completion gates:

```powershell
& $py .\scripts\compound_orchestrator.py check --target . --task-id 2026-05-21-add-billing-webhook-retry-handling
```

Audit the harness:

```powershell
& $py .\scripts\compound_orchestrator.py harness-check --target .
```

Start a coordinated team run:

```powershell
& $py .\scripts\compound_orchestrator.py team-start --target . --title "Refactor checkout flow" --mode claude-agent-team
```

For Codex, use the same topology but make Codex the lead integrator:

```powershell
& $py .\scripts\compound_orchestrator.py team-start --target . --title "Refactor checkout flow" --mode codex-parallel-agents
```

## Claude Code

This repository includes a native Claude Code plugin manifest at `.claude-plugin/plugin.json`. For local testing:

```bash
claude --plugin-dir . -p "Use /compound-init to explain how this repo bootstraps compound engineering."
claude plugin validate .
```

`init` also creates project-local `.claude/commands` and `.claude/agents` templates. They provide a stable Claude-side vocabulary:

- `/compound-start`
- `/compound-plan`
- `/compound-review`
- `/compound-learn`
- `/compound-init`
- `/compound-team-start`
- `/compound-harness-check`
- `compound-architect`
- `compound-reviewer`
- `compound-test-runner`

Claude Code agent teams are experimental and disabled by default, so `init` writes the required project setting. The runtime team config is still created and managed by Claude Code under `~/.claude/teams/`; this plugin only enables the feature and supplies reusable teammate roles plus the shared topology in `.agent-loop/team-topology.md`.

The plugin also ships hooks in `hooks/hooks.json`. `SessionStart` injects a short harness reminder, and `Stop` asks whether the session learned anything durable that should be captured in `CLAUDE.md` or durable docs before ending.

## Codex

The Codex skill in `skills/compound-orchestrator/SKILL.md` teaches Codex to use the same loop and the same artifacts. Codex remains responsible for respecting local workspace safety, test execution, and agent-spawn rules.

For Codex multi-agent work, use `.agent-loop/codex-parallel-contract.md`. Codex does not share Claude's runtime team mailbox, so the lead Codex session acts as the hub: it spawns bounded explorer/worker/reviewer agents, prevents same-file ownership conflicts, integrates results, verifies, and writes the compound note.

The generated `AGENTS.md`, `CODEBASE_MAP.md`, and `.agent-loop/harness-checklist.md` bring the same large-codebase harness rules to Codex: keep root context lean, layer local conventions deeper, deny noisy generated paths, and promote repeated instructions into skills or hooks.

## Test

```powershell
$py = "C:\Users\kenhu\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
& .\scripts\verify_plugin.ps1 -Python $py
```

WSL/Linux:

```bash
PYTHON=python3 ./scripts/verify_plugin.sh
```
