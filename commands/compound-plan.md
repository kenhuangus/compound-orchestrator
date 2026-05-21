---
name: compound-plan
description: Convert a compound task brief into a scoped work, README, and verification plan.
allowed-tools: Read, Grep, Glob, Bash, Write
---

Turn the current task brief into an implementation plan.

Include:

- files, drafts, or artifacts likely to change
- tests to add or run
- README sections likely to change or a note that README is unaffected
- risks and mitigations
- agent lanes with disjoint ownership
- completion gate checklist

Consult prior durable learning before proposing new structure:

- `docs/patterns/`
- `docs/decisions/`
- `docs/failures/`
- `.agent-loop/review-rubric.md`
