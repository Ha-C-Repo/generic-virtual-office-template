---
name: marathon-prequaltracker
description: >
  Track Your Company's Marathon Petroleum prequalification status and return
  a ranked list of open blockers. Tier 1 skill - only verified data,
  never fabricate a status or date.
triggers:
  - marathon status
  - marathon prequal
  - marathon petroleum status
  - prequal tracker
  - marathon blockers
  - check marathon
  - marathon approval status
---

# Marathon Petroleum Prequalification Tracker

## Context

Your Company, LLC is pursuing prequalification with Marathon Petroleum Company LP.
Prequalification runs through ISNetworld (Your Company Contractor ID: [ISN ID]).
Marathon may also use Avetta as an alternate prequalification platform.

All blockers must clear in sequence before Marathon can formally approve Your Company
as an approved contractor. This tracker aggregates all Marathon-specific blockers
into a single ranked view.

## Known Blockers (ranked by urgency)

| # | Blocker | Status | Owner | Contact / Next Action |
|---|---------|--------|-------|----------------------|
| 1 | EMR letter from Texas Mutual (Policy [POLICY NUMBER]) | ACTIVE BLOCKER | Joseph Hasse | Call Texas Mutual 800-859-5995 Monday 8am. Request EMR verification letter for ISNetworld upload. See emr-letter-drafter skill. |
| 2 | ISNetworld RAVS score maintenance (target >= 96) | MONITORING | Paul Guerrero (Safety Director, NCCER #27160819) | Check ISNetworld dashboard. Paul manages RAVS documentation. See isnetworld-ravs skill. |
| 3 | Auto Liability CSL requirement ($2M minimum) | STATUS UNKNOWN | The Owner / insurance broker | Verify current policy limits match Marathon requirements. Check Certificate of Insurance on file. |
| 4 | ISNetworld overall compliance score >= 400 | STATUS UNKNOWN | Joseph Hasse | Log in to ISNetworld ID [ISN ID] and check current score. Address any flagged deficiencies. |

## Output Format

When asked for marathon status, respond with this exact structure:

```
MARATHON PREQUAL TRACKER
As of: [date]
Overall: X of 4 blockers cleared

| # | Blocker | Status | Owner | Next Action |
|---|---------|--------|-------|------------|
| 1 | EMR letter (Texas Mutual) | [status] | Joseph | [action] |
| 2 | RAVS score >= 96 (ISNetworld) | [status] | Paul G. | [action] |
| 3 | Auto Liability CSL $2M | [status] | Owner | [action] |
| 4 | ISN compliance score >= 400 | [status] | Joseph | [action] |

NEXT STEP: [single highest-priority unresolved action]
```

## Rules

- Never fabricate a blocker status, date, or score.
- If data is unavailable, say "unknown - check ISNetworld manually" not a guess.
- Blocker list must be ranked: highest urgency first.
- Surface blocker 1 (EMR letter) prominently until the upload to ISNetworld is confirmed.
- A blocker is CLEARED only when its specific action is confirmed complete. Do not mark CLEARED based on assumption.
- When a blocker resolves, move it to a Cleared section at the bottom. Do not delete it from history.
- Do not report Marathon approval as complete until ALL four blockers show CLEARED.
- If Marathon switches from ISNetworld to Avetta mid-process, note the platform change and flag that the Avetta blocker set is not yet documented.

## Avetta Fallback

Marathon Petroleum may use Avetta as an alternate prequalification platform.

- If the ISNetworld path stalls, check whether Marathon has requested Avetta onboarding.
- Avetta prequalification has its own blocker set, distinct from ISNetworld.
- If Avetta becomes the primary platform, document its blockers and update this tracker.
- Note which platform Marathon is using at the time of any status query.

## Morning Briefing Integration

- Until all four blockers clear, surface this tracker under "Active Blockers" with priority HIGH.
- Blocker 1 (EMR letter) remains the top morning briefing item until upload is confirmed.
- When the last blocker clears, change the entry to RESOLVED and notify Owner.
- Do not downgrade priority until ISNetworld formally shows the prequalification as approved.

## Cross-references

- EMR letter request: see emr-letter-drafter skill.
- ISNetworld RAVS documentation: see isnetworld-ravs skill.
- Safety Director contact: Paul Guerrero, NCCER #27160819.
- Your Company ISNetworld ID: [ISN ID].
- Texas Mutual: 800-859-5995, Policy [POLICY NUMBER].
