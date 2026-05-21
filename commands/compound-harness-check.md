---
name: compound-harness-check
description: Audit whether the repository has a practical large-codebase Claude/Codex harness.
allowed-tools: Read, Grep, Glob, Bash
---

Audit the current repository's compound engineering harness.

Run:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/compound_orchestrator.py" harness-check --target .
```

Then summarize:

- missing navigability files
- whether `CLAUDE.md` is lean and layered
- whether generated/vendor/build files are denied in `.claude/settings.json`
- whether hooks, path-scoped skill templates, LSP/MCP roadmap, and ownership cadence exist
- highest-leverage next fix
