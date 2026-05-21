---
name: compound-review
description: Review a task diff against the compound engineering rubric and identify learnings to capture.
allowed-tools: Read, Grep, Glob, Bash
---

Review the current diff using `.agent-loop/review-rubric.md`.

Lead with findings ordered by severity. Include file and line references when possible. Call out missing verification and any lesson that should become a durable compound note.

Check:

- correctness and edge cases
- security and data integrity
- product or UX regressions
- missing tests
- repeated failures from `docs/failures/`
- new reusable patterns or decisions
