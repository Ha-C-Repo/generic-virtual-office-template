---
name: code-quality-loop
description: Use when writing, editing, reviewing, refactoring, or debugging code in this project. Enforces a plan-first, small-diff, verify-before-ship workflow so generated code is checked against the real codebase and tested rather than shipped on faith. Covers planning, context hygiene, independent review, a test-feedback-repair harness loop, and accuracy guardrails. Use this whenever a task produces or changes code, even if the request does not say "review" or "test".
---

# Code quality loop

Goal: produce correct, deliberate code, not slop. Five habits.

## 1. Plan before code
Write the intended change in a short plan first (a PLAN.md, or an inline plan in
the reply), then check that plan against the actual code before generating any
diff. The plan must describe what the code really does, not what the model
assumes it does. If the plan and the code disagree, fix the plan first.

## 2. Small diffs, reset before quality drops
Keep each change small and reviewable. Refresh or hand off the session before
output quality degrades, not after it has already slipped. A rough starting
heuristic is to reset while there is still healthy context budget left rather
than running to exhaustion. Tune the threshold per environment.

## 3. Independent review in a fresh session
A session that wrote the code tends to approve its own work. Review in a fresh
session, one concern at a time: correctness first, then edge cases, then
security, and so on. A focused fresh pass finds what the original missed. This
is independent verification, not a second opinion from the same context.

## 4. Harness loop: verify before ship
After writing, run the relevant tests or checks. On failure, fix and re-verify.
Do not present code as done until it has passed a real check. If no test covers
the change, add a minimal one or state plainly that the change is unverified.
This is the test-feedback-repair loop: the code earns "done", it is not assumed.

## 5. Accuracy guardrails (fill in per project)
- Single source of truth per data type. Defer to the project's authoritative
  source or validator. A model guess never overrides it.
- No fabricated values. If a number, name, path, or fact cannot be traced to a
  real source, mark it unknown and stop. Do not estimate into a deliverable.
- Cite the source for any figure or claim that has one.
- Human gate before anything ships externally, where the project requires it.
- Flag low confidence instead of guessing.

## Open research questions
For open, divergent questions where one answer is risky, use the panel-and-judge
skill. Keep it out of any path that has a single source of truth.

---

Keep this detail in this skill file. The project's CLAUDE.md should only point
to this skill by name, not copy its contents.
