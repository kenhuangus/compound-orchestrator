# Compound Orchestrator

Compound Orchestrator is a small Codex and Claude Code plugin plus project bootstrapper for running a consistent compound engineering loop across both tools.

It complements the EveryInc Compound Engineering plugin by adding project-level guardrails:

- shared Codex and Claude Code operating memory
- Claude slash-command and subagent templates
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
- `compound-architect`
- `compound-reviewer`
- `compound-test-runner`

## Codex

The Codex skill in `skills/compound-orchestrator/SKILL.md` teaches Codex to use the same loop and the same artifacts. Codex remains responsible for respecting local workspace safety, test execution, and agent-spawn rules.

## Test

```powershell
$py = "C:\Users\kenhu\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
& .\scripts\verify_plugin.ps1 -Python $py
```

WSL/Linux:

```bash
PYTHON=python3 ./scripts/verify_plugin.sh
```
