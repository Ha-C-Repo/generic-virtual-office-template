---
name: cowork-cheat-sheet
description: >
  Full command reference for the Your Company Virtual Office via Cowork.
  Returns a tight table of all available slash commands and natural language
  equivalents. Use when Owner says "help", "what can I do", or "command list".
triggers:
  - help
  - what can I do
  - command list
  - bid commands
  - show commands
  - what commands
  - list commands
---

# Cowork Command Reference

## Triggers

Fire this skill when the user message contains any of:
- "help"
- "what can I do"
- "command list"
- "bid commands"
- "show commands"
- "what commands"
- "list commands"

## Output

Return the table below. No prose before or after except the closing line.

---

**Your Company Virtual Office - Command Reference**

| Command | What it does |
|---|---|
| /morning-brief | Today's intel: steel prices, open bids, compliance blockers, shop status |
| /intake-bid | Start a new bid from an invite email or scope description |
| /takeoff | Process a structural drawing PDF - extracts members and quantities |
| /price-bid | Generate pricing from takeoff data using locked Q2 2026 rates |
| /gp-only | Generate the internal GP report for an existing bid |
| /check-compliance | Run 6-gate compliance check: ISN, DISA, EMR, AISC, AWS, Special Inspector |
| /go-no-go | Score a bid for pipeline pursuit - returns PURSUE / PASS / HOLD |
| /score-bid | Pipeline score for a specific bid |
| /list-bids | All active bids with current status |
| /approvals | Bids waiting for the Owner's review |

**Natural language equivalents:**

| Say this | Same as |
|---|---|
| "morning brief" or "what's on the board" | /morning-brief |
| "new bid" or "intake this invite" | /intake-bid |
| "take off these drawings" | /takeoff |
| "price this bid" | /price-bid |
| "check compliance for [project]" | /check-compliance |
| "should we pursue [project]" | /go-no-go |
| "show my bids" or "pipeline" | /list-bids |
| "what needs my approval" | /approvals |

Say any of the above. No special syntax needed.
