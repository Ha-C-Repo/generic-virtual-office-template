---
name: panel-and-judge
description: Use for open, divergent, or research-heavy questions where one model's answer is risky and you want breadth plus a synthesized judgment: option comparisons, design tradeoffs, ambiguous strategy calls, "what are the options", or framing a hard problem. Run the question across several models or sessions, then synthesize one answer that names consensus, conflicts, and gaps. Do not use this on any task that has a single source of truth or authoritative numbers; defer to the source for those. Reach for this when the question is open, not when the answer must be looked up.
---

# Panel and judge

A way to reduce single-model blind spots on open questions. Fan out, then judge.

## When to use
Open, divergent, or research-heavy questions: comparing options, weighing design
tradeoffs, exploring an ambiguous problem, sketching strategy, or any case where
one model's confident answer could quietly be wrong.

## When not to use
Any path with a single source of truth or an authoritative number. For those,
defer to the source or validator. Synthesis across guesses does not make a guess
correct. Do not use this to average facts.

## How to run
1. Fix the exact question once, so every panelist answers the same thing.
2. Fan out: send that question to several models or fresh sessions in parallel.
   Keep them independent; do not let one see another's answer.
3. Collect the raw answers.

## The judge step
Hand all answers to one judge step (a fresh session is fine) and ask it to
produce a single synthesized answer that names:
- consensus: what they agree on,
- conflicts: where they disagree, and which side is better supported,
- gaps: what none of them covered,
- unique insight: anything one panelist caught that the others missed.
The judge should reason about which claims are supported, not just tally votes.

## How to present
Give one synthesized answer, then a short note on where the panel disagreed and
why you landed where you did. Do not paste every raw answer unless asked.

## Guardrails
- Keep it opt-in. This is a mode you choose, not a default for every question.
- Treat any benchmark or performance numbers cited for this technique as
  unverified marketing unless you can confirm them from a primary source.
- Never apply it to single-source-of-truth data. See code-quality-loop for that
  boundary.

---

Keep this detail here. The project's CLAUDE.md should point to this skill by
name, not copy its contents.
