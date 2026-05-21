# Compound Orchestrator

Compound Orchestrator is a reusable plugin and project bootstrapper for making agent-assisted work compound over time. It installs a shared harness for coding, writing, research, documentation, and mixed projects so every meaningful task leaves behind a plan, review, verification trail, ownership record, README update when relevant, and durable learning for the next task.

It works across Windows, macOS, Linux, and WSL. Claude Code and Codex get first-class support, and any other agent runtime can participate by using the same generated CLI, ownership file, review rubric, and cross-platform verifier.

## What It Gives You

- `README.md` maintenance policy for keeping project docs current instead of stale.
- `AGENTS.md` and `CLAUDE.md` managed protocol blocks for shared agent behavior.
- Claude Code slash commands, subagent definitions, hooks, and agent-team enablement.
- A Codex parallel-agent contract that mirrors the Claude team topology.
- Generic ownership claims so Claude Code, Codex, Cursor, Aider, CI agents, or future tools can avoid overlapping edits.
- Cross-tool review roles so one agent runtime reviews work authored by another.
- Project maps, task briefs, review rubrics, handoff templates, scorecards, and durable learning folders.
- Portable generated scripts: `scripts/compound_orchestrator.py`, `scripts/verify.py`, `scripts/verify.ps1`, and `scripts/verify.sh`.

## Supported Work

Use this plugin for:

- Coding projects: apps, libraries, services, monorepos, scripts, tests, and deployment workflows.
- Writing projects: essays, reports, manuscripts, chapters, documentation sites, source notes, and export workflows.
- Research or mixed projects: analysis, notebooks, docs, code, reviews, and artifacts that need coordinated agent work.

The core loop is:

```text
brainstorm -> plan -> work -> review -> compound -> repeat
```

The final step is the point. Each completed task should improve the next task by recording a reusable pattern, decision, failure note, review, or compound note.

## Install Into A Project

From this plugin directory on Windows PowerShell:

```powershell
$py = "python"
& $py .\scripts\compound_orchestrator.py init --target "C:\path\to\project"
& $py .\scripts\compound_orchestrator.py check --target "C:\path\to\project"
```

If `python` is not configured on Windows, point `$py` at a virtualenv, system Python, or bundled agent runtime Python.

From macOS, Linux, or WSL:

```bash
python3 scripts/compound_orchestrator.py init --target /path/to/project
python3 scripts/compound_orchestrator.py check --target /path/to/project
```

The initializer is conservative. It creates missing files, appends managed blocks to existing `README.md`, `AGENTS.md`, and `CLAUDE.md`, and preserves local content unless `--force` is used for generated files.

After initialization, the target project is portable. Agents can run the copied project-local CLI:

```bash
python3 scripts/compound_orchestrator.py check --target .
python3 scripts/verify.py
```

## README Maintenance

`README.md` is part of the product. Update it whenever setup, usage, architecture, workflow, commands, generated outputs, public behavior, manuscript structure, export process, or review workflow changes.

Every README update should:

1. Remove old information that is no longer true.
2. Keep unchanged information that is still useful.
3. Add the new information readers need.
4. Reorganize the README so it is easy to follow and reflects the latest project state.

The plugin installs this rule into generated projects through both the managed README block and `.agent-loop/readme-maintenance.md`.

## Daily Workflow

Start a task:

```bash
python3 scripts/compound_orchestrator.py start --target . --title "Add billing webhook retry handling"
```

Start a team run:

```bash
python3 scripts/compound_orchestrator.py team-start --target . --title "Refactor checkout flow" --mode codex-parallel-agents
```

Claim files or artifacts before editing:

```bash
python3 scripts/compound_orchestrator.py claim --target . --tool codex --agent codex-worker --task-id TASK --paths src/payment.py --intent "Implement retry handling"
```

Use any lowercase runtime label for `--tool`, such as `claude`, `codex`, `cursor`, `aider`, or `ci`. A claim fails if another active agent owns an overlapping path.

Release claims after integration or handoff:

```bash
python3 scripts/compound_orchestrator.py release --target . --tool codex --agent codex-worker --task-id TASK
```

Record opposite-tool review:

```bash
python3 scripts/compound_orchestrator.py cross-review --target . --task-id TASK --reviewer-tool claude --author-tool codex --summary "Claude reviewed Codex-authored retry handling."
```

Record durable learning:

```bash
python3 scripts/compound_orchestrator.py learn --target . --kind failure --title "Webhook duplicate invoice" --summary "Provider retries can arrive after the DB write succeeds. Future handlers must use idempotency keys."
```

## Verification

Generated projects get three platform entrypoints:

```bash
python3 scripts/verify.py
sh scripts/verify.sh
```

```powershell
.\scripts\verify.ps1
```

The verifier checks compound files, README maintenance markers, Claude agent-team settings, ownership conflicts, Markdown conflict markers, Python unittest suites, and common npm scripts when present.

Use `--compound-only` when you want to verify only the harness:

```bash
python3 scripts/verify.py --compound-only
```

## Claude Code

The Claude plugin manifest is `.claude-plugin/plugin.json`. Local validation:

```bash
claude plugin validate .
claude --plugin-dir . plugin details compound-orchestrator
```

The initializer writes project-local `.claude/commands` and `.claude/agents` templates, including:

- `/compound-start`
- `/compound-plan`
- `/compound-review`
- `/compound-learn`
- `/compound-init`
- `/compound-team-start`
- `/compound-harness-check`
- `/compound-claim`
- `/compound-release`
- `/compound-ownership-status`
- `/compound-cross-review`
- `compound-architect`
- `compound-reviewer`
- `compound-test-runner`
- `compound-cross-tool-reviewer`

It also enables Claude Code agent teams by merging `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` into `.claude/settings.json`. Claude still owns its runtime team files under `~/.claude/teams/`; this plugin supplies the project harness and reusable teammate roles.

## Codex And Other Agents

Codex uses `skills/compound-orchestrator/SKILL.md` and `skills/codex-cross-tool-reviewer/SKILL.md` to follow the same loop. For parallel work, Codex acts as the lead integrator, spawns bounded explorer/worker/reviewer agents when useful, claims disjoint write scopes, integrates results, verifies, and writes the compound note.

Other agents can participate by following the generated project files:

- `AGENTS.md`
- `CODEBASE_MAP.md`
- `.agent-loop/team-topology.md`
- `.agent-loop/codex-parallel-contract.md`
- `.agent-loop/cross-tool-protocol.md`
- `.agent-loop/coordination/ownership.json`
- `.agent-loop/review-rubric.md`
- `.agent-loop/readme-maintenance.md`

They do not need Claude's runtime team mailbox or Codex's chat interface. They only need to respect the shared claims, artifacts, verifier, and review gate.

## Commands

| Command | Purpose |
| --- | --- |
| `init` | Install the project harness. |
| `check` | Check required files, managed blocks, settings, ownership, and optional task gates. |
| `harness-check` | Audit project readiness for scalable agent work. |
| `start` | Create brainstorm and plan artifacts for one task. |
| `team-start` | Create artifacts for a Claude or Codex multi-agent run. |
| `claim` | Claim files, directories, drafts, or artifacts before editing. |
| `release` | Release active ownership claims. |
| `ownership-status` | Show active claims and conflicts. |
| `cross-review` | Record a review by one runtime of another runtime's work. |
| `learn` | Write a durable pattern, decision, failure, review, or compound note. |
| `self-test` | Validate this plugin package and generated project behavior. |

## Test This Plugin

Windows:

```powershell
$py = "python"
& .\scripts\verify_plugin.ps1 -Python $py
```

macOS, Linux, or WSL:

```bash
PYTHON=python3 ./scripts/verify_plugin.sh
```

The plugin repository is public at [github.com/kenhuangus/compound-orchestrator](https://github.com/kenhuangus/compound-orchestrator).
