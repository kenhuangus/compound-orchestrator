# Compound Learning: Planning Contracts And Two-Round Review

Date: `2026-05-22`
Kind: `compound`

## What Compounded

The Agentic IAM validation project showed that the loop improves when planning is treated as a contract, not a preamble. Adding `prd.html`, `planning.html`, `spec.html`, `test-cases.html`, `architecture.html`, and `users.html` made it obvious where ambiguity should live and when implementation is premature.

## Reuse Rule

For substantial projects, parallelize only the independent planning drafts first: PRD, users/workflows, architecture, planning, and early test-risk discovery. Then serialize the integration pass, `spec.html`, `test-cases.html`, and two-round review. This avoids fast but inconsistent plans.

## Review Rule

`compound-cross-review` must include author action, not just reviewer commentary:

1. Round 1 review.
2. Author response/revision.
3. Round 2 review.
4. Author response/revision.
5. Final acceptance.

Stop after two rounds unless the user explicitly asks for more.

## Test Trace Lesson

`test-cases.html` should be derived from `spec.html` and explicitly cover happy paths, edge cases, error cases, performance cases, user workflow cases, and acceptance criteria. In the Agentic IAM fixture this forced deny-overrides-allow, invalid policy authoring, and default-deny behavior into tests instead of leaving them as prose.

## Future Prompting Change

When using Compound Orchestrator, ask agents for:

- owned planning artifact
- dependency phase
- expected revision artifact
- verification command
- compound note

Do not ask agents to "review" without also naming who must revise and where the response artifact goes.
