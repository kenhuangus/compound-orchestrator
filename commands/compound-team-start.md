---
name: compound-team-start
description: Start a Claude Code agent team or Codex parallel-agent run with shared ownership and learning gates.
allowed-tools: Read, Grep, Glob, Bash, Write
---

Start a multi-agent compound engineering run.

First create the shared artifacts:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/compound_orchestrator.py" team-start --target . --title "$ARGUMENTS" --mode claude-agent-team
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/compound_orchestrator.py" check --target .
```

Then create a Claude Code agent team in natural language:

```text
Create an agent team for this task. Use `.agent-loop/team-topology.md`.
Spawn a `compound-architect`, a `compound-test-runner`, and a `compound-reviewer`.
Only add an implementer teammate if the write scope is disjoint and clear.
Keep the team to 3-5 teammates, wait for them to finish, synthesize findings, run verification, and write a compound note.
```

If running the same shape in Codex, use `.agent-loop/codex-parallel-contract.md` and keep the lead session responsible for decomposition, integration, verification, and the final compound note.
