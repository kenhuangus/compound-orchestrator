---
name: compound-deliverables-check
description: Check planning contracts, two-round review artifacts, verification, README freshness, and compound learning before handoff.
allowed-tools: Read, Grep, Glob, Bash
---

Use this before implementation begins and again before final delivery.

Run:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/compound_orchestrator.py" check --target . --task-id TASK_ID
```

The gate expects:

- `prd.html`
- `planning.html`
- `spec.html`
- `test-cases.html`
- `architecture.html` with `architecture.excalidraw`
- `users.html`
- `docs/cross-reviews/TASK_ID/round-1-review.md`
- `docs/cross-reviews/TASK_ID/round-1-response.md`
- `docs/cross-reviews/TASK_ID/round-2-review.md`
- `docs/cross-reviews/TASK_ID/round-2-response.md`
- `docs/cross-reviews/TASK_ID/final-acceptance.md`
- review and compound notes

If the command fails, fix the missing artifact instead of declaring completion.
