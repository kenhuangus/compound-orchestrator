---
name: compound-plan
description: Convert a compound task brief into a scoped implementation and verification plan.
allowed-tools: Read, Grep, Glob, Bash, Write
---

Turn the current task brief into an implementation plan.

Include:

- files likely to change
- tests to add or run
- risks and mitigations
- agent lanes with disjoint ownership
- completion gate checklist

Consult prior durable learning before proposing new structure:

- `docs/patterns/`
- `docs/decisions/`
- `docs/failures/`
- `.agent-loop/review-rubric.md`
