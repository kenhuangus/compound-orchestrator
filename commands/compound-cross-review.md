---
name: compound-cross-review
description: Run the required two-round Codex/Claude cross-tool review protocol and record each stage.
allowed-tools: Read, Grep, Glob, Bash
---

Use this when Claude Code and Codex review planning artifacts, implementation, writing, or other authored work across tools.

1. Inspect active claims:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/compound_orchestrator.py" ownership-status --target .
```

2. Review the authoring agent's diff or paths assigned by the lead.
3. Cover the six planning artifacts when this is a planning gate: `prd.html`, `planning.html`, `spec.html`, `test-cases.html`, `architecture.html`, and `users.html`.
4. Record exactly two rounds unless the user asks for more:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/compound_orchestrator.py" cross-review --target . --task-id TASK_ID --reviewer-tool codex --author-tool claude --stage round-1-review --summary "Round 1 findings..."
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/compound_orchestrator.py" cross-review --target . --task-id TASK_ID --reviewer-tool claude --author-tool codex --stage round-1-response --summary "Claude addressed round 1..."
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/compound_orchestrator.py" cross-review --target . --task-id TASK_ID --reviewer-tool codex --author-tool claude --stage round-2-review --summary "Round 2 findings..."
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/compound_orchestrator.py" cross-review --target . --task-id TASK_ID --reviewer-tool claude --author-tool codex --stage round-2-response --summary "Claude addressed round 2..."
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/compound_orchestrator.py" cross-review --target . --task-id TASK_ID --reviewer-tool codex --author-tool claude --stage final-acceptance --summary "Accepted after two rounds."
```

Do not declare the task complete until the authoring tool has addressed comments after each review round.
