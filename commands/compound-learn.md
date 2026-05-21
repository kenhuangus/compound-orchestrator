---
name: compound-learn
description: Finish a task by writing durable compound learning and checking the completion gate.
allowed-tools: Read, Grep, Glob, Bash, Write, Edit
---

Finish the task by writing durable learning.

Record at least one of:

- pattern in `docs/patterns/`
- decision in `docs/decisions/`
- failure in `docs/failures/`
- task compound note in `docs/compound/`

Update `AGENTS.md` and `CLAUDE.md` only when the lesson should affect all future work.

Before declaring done, run:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/compound_orchestrator.py" check --target .
```

If the task id is known, include:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/compound_orchestrator.py" check --target . --task-id TASK_ID
```
