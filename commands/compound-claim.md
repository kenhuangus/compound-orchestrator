---
name: compound-claim
description: Claim files before editing so Claude Code, Codex, and other agents do not collide.
allowed-tools: Bash, Read
---

Claim files, directories, drafts, or artifacts before editing.

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/compound_orchestrator.py" claim --target . --tool claude --agent "$USER" --task-id TASK_ID --paths path/to/file.py --intent "Describe planned edit"
```

If the claim fails, do not edit the file. Ask the lead integrator to narrow scopes, release stale claims, or serialize the work.
