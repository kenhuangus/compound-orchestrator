---
name: compound-init
description: Initialize the current repository for cross-platform compound engineering across agents.
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

Also confirm that `.claude/settings.json` enables Claude Code agent teams with `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`, `README.md` contains the managed maintenance policy, and generated projects have `scripts/compound_orchestrator.py`, `scripts/verify.py`, `scripts/verify.ps1`, and `scripts/verify.sh`.

Point Codex and other agent users to `.agent-loop/codex-parallel-contract.md`, `.agent-loop/cross-tool-protocol.md`, and `.agent-loop/readme-maintenance.md`.
