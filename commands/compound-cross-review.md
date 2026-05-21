---
name: compound-cross-review
description: Review Codex-authored or other-agent-authored changes from Claude Code and record a cross-tool review.
allowed-tools: Read, Grep, Glob, Bash
---

Use this when Claude Code reviews Codex-authored or other-agent-authored changes.

1. Inspect active claims:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/compound_orchestrator.py" ownership-status --target .
```

2. Review the authoring agent's diff or paths assigned by the lead.
3. Record the review:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/compound_orchestrator.py" cross-review --target . --task-id TASK_ID --reviewer-tool claude --author-tool codex --summary "Reviewed Codex-authored changes and found ..."
```
