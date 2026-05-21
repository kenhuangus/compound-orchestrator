---
name: compound-start
description: Start a compound engineering task with a task brief, plan, README awareness, and clear agent lanes.
allowed-tools: Read, Grep, Glob, Bash, Write
---

Start a meaningful task using the compound engineering protocol.

Steps:

1. Restate the goal and definition of done.
2. Inspect `STRATEGY.md`, `README.md`, `AGENTS.md`, `CLAUDE.md`, and relevant `docs/patterns`, `docs/decisions`, and `docs/failures`.
3. If the repository has not been initialized, run the Compound Orchestrator initializer.
4. Create a plan in `docs/plans/` using `.agent-loop/task-brief-template.md`.
5. Identify parallel agent lanes only when the lanes are independent and have clear ownership.
6. Stop before implementation if ownership, verification, or README impact is unclear.

Use the plugin CLI when available:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/compound_orchestrator.py" start --target . --title "$ARGUMENTS"
```
