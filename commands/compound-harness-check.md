---
name: compound-harness-check
description: Audit whether the repository has a practical cross-agent project harness.
allowed-tools: Read, Grep, Glob, Bash
---

Audit the current repository's compound engineering harness.

Run:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/compound_orchestrator.py" harness-check --target .
```

Then summarize:

- missing navigability files and README maintenance policy
- whether `CLAUDE.md` is lean and layered
- whether generated/vendor/build files are denied in `.claude/settings.json`
- whether hooks, path-scoped skill templates, LSP/MCP roadmap, and ownership cadence exist
- whether cross-platform verification exists through `scripts/verify.py`, `scripts/verify.ps1`, and `scripts/verify.sh`
- highest-leverage next fix
