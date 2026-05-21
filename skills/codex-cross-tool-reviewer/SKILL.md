---
name: codex-cross-tool-reviewer
description: Use when Codex reviews Claude Code-authored changes or verifies Claude/Codex ownership claims before integration.
---

# Codex Cross-Tool Reviewer

Use this skill when Codex is asked to review code written by Claude Code or a Claude teammate.

## Required Checks

1. Inspect `.agent-loop/coordination/ownership.json`.
2. Confirm Claude Code edited only claimed files.
3. Check for active overlapping claims between Claude and Codex.
4. Review correctness, security, tests, and maintainability.
5. Record the result with:

```powershell
& <python> <plugin-root>\scripts\compound_orchestrator.py cross-review --target <project-root> --task-id <task-id> --reviewer-tool codex --author-tool claude --summary "<findings summary>"
```

## Review Stance

Lead with findings ordered by severity. If there are no findings, say that clearly and list any residual risk or missing verification.

Do not edit files during cross-review unless the lead integrator explicitly assigns a patch and the intended files have been claimed.
