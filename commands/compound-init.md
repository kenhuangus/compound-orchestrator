---
name: compound-init
description: Initialize the current repository for consistent Codex and Claude Code compound engineering.
allowed-tools: Bash, Read, Write
---

Initialize the current repository for compound engineering.

Run:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/compound_orchestrator.py" init --target .
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/compound_orchestrator.py" check --target .
```

Then summarize the created files and the daily loop:

```text
brainstorm -> plan -> work -> review -> compound
```

Also confirm that `.claude/settings.json` enables Claude Code agent teams with `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`, and point Codex users to `.agent-loop/codex-parallel-contract.md` for the matching parallel-agent workflow.
