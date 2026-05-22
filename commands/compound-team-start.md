---
name: compound-team-start
description: Start a Claude Code agent team, Codex parallel-agent run, or compatible agent-team workflow with shared ownership and learning gates.
allowed-tools: Read, Grep, Glob, Bash, Write
---

Start a multi-agent compound engineering run.

First create the shared artifacts:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/compound_orchestrator.py" team-start --target . --title "$ARGUMENTS" --mode claude-agent-team
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/compound_orchestrator.py" check --target .
```

Then create a dependency-aware Claude Code agent team in natural language:

```text
Create an agent team for this task. Use `.agent-loop/team-topology.md`, `.agent-loop/core-planning-artifacts.md`, and `.agent-loop/parallel-agent-team-protocol.md`.
Parallelize PRD, users/workflow, architecture, planning, and early test strategy.
Serialize integration, spec creation, test-case finalization, and final acceptance.
Do not start implementation until `prd.html`, `planning.html`, `spec.html`, `test-cases.html`, `architecture.html`, and `users.html` pass two cross-review rounds.
Keep write scopes disjoint, wait for teammates to finish, synthesize findings, run verification, and write a compound note.
```

If running the same shape in Codex or another agent runtime, use `.agent-loop/codex-parallel-contract.md` and keep the lead session responsible for decomposition, disjoint ownership, integration, verification, README updates when relevant, and the final compound note.
