---
name: compound-plan
description: Convert a compound task brief into a scoped work, README, and verification plan.
allowed-tools: Read, Grep, Glob, Bash, Write
---

Turn the current task brief into an implementation plan.

Include:

- six core planning artifacts: `prd.html`, `planning.html`, `spec.html`, `test-cases.html`, `architecture.html`, and `users.html`
- files, drafts, or artifacts likely to change
- tests to add or run
- README sections likely to change or a note that README is unaffected
- risks and mitigations
- agent lanes with disjoint ownership
- completion gate checklist

Planning is dependency-aware: parallelize PRD, users, architecture, planning, and test-risk drafting; then serialize integration, `spec.html`, `test-cases.html`, two-round review, and final acceptance.

Consult prior durable learning before proposing new structure:

- `docs/patterns/`
- `docs/decisions/`
- `docs/failures/`
- `.agent-loop/review-rubric.md`
- `.agent-loop/core-planning-artifacts.md`
- `.agent-loop/parallel-agent-team-protocol.md`
- `.agent-loop/two-round-review-protocol.md`
