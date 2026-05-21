---
name: compound-release
description: Release file ownership claims after a Claude/Codex task is integrated, abandoned, or handed off.
allowed-tools: Bash
---

Release ownership claims.

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/compound_orchestrator.py" release --target . --tool claude --agent "$USER" --task-id TASK_ID
```
