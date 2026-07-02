---
name: two-pdf-pair-check
description: >
  Enforces the two-PDF rule: every bid requires both a client proposal PDF
  and an internal GP report PDF with the -GP suffix. Checks that both files
  exist after generation. Blocks delivery if the pair is incomplete.
triggers:
  - two pdf check
  - pdf pair
  - check pdfs
  - missing gp report
  - gp report missing
  - two pdfs
  - pdf pairing
  - check the pdfs
---

# Two-PDF Pair Check

## The Rule

Every bid produces exactly two PDFs:
1. Client proposal: `<project>_<date>.pdf`
2. Internal GP report: `<project>_<date>-GP.pdf`

The `-GP` suffix is the convention. Both files must exist before delivery.
The GP report is never sent to clients or external parties.

## When to run

- After any `generate_proposal()` or `generate_gp_report()` call
- Before marking a bid as "ready to send"
- Any time Owner or Joseph asks to check bid PDFs
- On any "is this ready to go out?" request involving a bid

## Check procedure

Given a bid name or output path:

1. Identify the expected proposal PDF name: `<project>_<date>.pdf`
2. Identify the expected GP report PDF name: `<project>_<date>-GP.pdf`
3. Check that both files exist in `output/`.
4. If both exist: PASS. Report file sizes and confirm the pair.
5. If GP report missing: attempt to generate it via `generate_gp_report()`.
   If generation succeeds: PASS. Log that it was auto-generated.
   If generation fails: BLOCK. Surface the error. Do not mark bid ready.
6. If client proposal missing: BLOCK. Cannot send what does not exist.

## Output format

```
TWO-PDF PAIR CHECK
Bid: [bid name]

Client proposal:  [filename]  [size]  FOUND / MISSING
GP report:        [filename]  [size]  FOUND / MISSING / AUTO-GENERATED

Result: PASS / BLOCK
[If BLOCK: reason and next step]
```

## Hard rules

- Never swap the two PDFs. Client gets the proposal, Owner keeps the GP.
- Never email the -GP report externally. It contains internal cost basis.
- If generation fails, do not send either PDF until both exist.
- The client PDF has NO internal margin data. The GP report has it all.
- Deck is always in scope. If either PDF omits deck, flag immediately.

## Naming reference

Standard naming: `EliteCrossing_Ph2_2026-05-16.pdf` (client)
                 `EliteCrossing_Ph2_2026-05-16-GP.pdf` (internal)

If PDFs are named differently (e.g. manual override), match by looking for
the `-GP` suffix on a file with an otherwise identical base name.
