# CLAUDE.md - Project Routing Map
# {{PROJECT_NUMBER}} - {{PROJECT_NAME}}
# Generated: {{CREATED_AT}}

## Project Identity

- **Project number:** {{PROJECT_NUMBER}}
- **Project name:** {{PROJECT_NAME}}
- **GC company:** {{GC_COMPANY}}
- **GC contact:** {{GC_CONTACT_EMAIL}}
- **Location:** {{LOCATION}}
- **Bid deadline:** {{DEADLINE}}
- **Estimated value:** {{ESTIMATED_VALUE}}
- **Tonnage estimate:** {{TONNAGE}}
- **Bid state:** {{BID_STATE}}
- **Pipeline ID:** {{BID_ID}}

## Folder Map (9-folder structure + operational tracking)

```
{{PROJECT_NUMBER}} - {{PROJECT_NAME}}/
  1.Bid-Invite/       original invitation, scope narrative, RFI
  2.Drawings/         structural PDFs, revision log
  3.Estimate/
    Takeoff/          VJ takeoff graph outputs
    Pricing/          generate_proposal_from_bid outputs
    Sanity-Gate/      run_gates() JSON results
  4.Proposal/         client PDF, GP report (-GP suffix)
  5.Compliance/       ISN status, DISA, EMR, certs
  6.Execution/        shop drawings, fab packages, AISC certs
  7.Field/            erection sequence, inspection reports, QC
  8.Financial/        AIA G702/G703, payment apps, invoices
  9.Operational/      (added 2026-05-27 from ConstructIQ pattern)
    Correspondence/
      Incoming/         received emails, letters, transmittals
      Outgoing/         sent emails, letters, RFIs
      Correspondence_Log.md   chronological index
    Registers/
      RFI_Register.md             RFI number, date, subject, status, response date
      Variation_Register.md       VO number, scope, $$ impact, schedule impact, status
      Submittal_Register.md       submittal number, spec section, status, return date
    Programme/
      Master_Programme_Rev.pdf    current rev only
      Milestones.md               key dates, dependency notes, slippage flags
      Schedule_Impact_Log.md      events that shifted the critical path
  Project OS/
    CLAUDE.md         this file - routing map
    State.md          pipeline_score output (syncer-written)
    Compliance.md     compliance_grade output (syncer-written)
    Activity.md       engagement records (syncer-written)
```

The `9.Operational/` sub-tree is for things that get tracked whether
we have folders for them or not - RFIs, VOs, submittals, programme
slippage. Keeping them in a defined location lets `/quote-leveling`,
`/variation-impact`, and `/programme-check` slash commands find them
without per-project setup. Source: ConstructIQ pattern adapted to
Your Company workflow on 2026-05-27.

## AI Routing Rules for This Project

When working on this project, route tasks as follows:

- Drawing takeoff -> `Bridge.auto_process_drawing(pdf_path=...)`
- Pricing / proposal -> `Bridge.generate_proposal_from_bid(bid_id={{BID_ID}})`
- GP report only -> `Bridge.generate_gp_only(bid_id={{BID_ID}})`
- Compliance check -> `Bridge.cascade_compliance()`
- Go/no-go review -> `Bridge.go_no_go_review(bid_id={{BID_ID}})`
- Score this bid -> `Bridge.pipeline_score(bid_id={{BID_ID}})`
- Compliance state -> `Bridge.get_compliance_status()`

## Operational Tracking Slash Commands

These read the `9.Operational/` sub-tree above. Each command names the
file it parses, so format consistency matters more than fancy content.

- `/quote-leveling` -> reads `3.Estimate/Pricing/Subcontractor_Quotes.md`,
  outputs a leveled comparison table.
- `/scope-gap-scan` -> reads `3.Estimate/Pricing/BOQ.xlsx` and matches each
  line to a sub-quote. Flags rows with no coverage.
- `/variation-impact` -> reads `9.Operational/Registers/Variation_Register.md`,
  returns total $ and schedule impact, grouped by status.
- `/programme-check` -> reads `9.Operational/Programme/Milestones.md` and
  `Master_Programme_Rev.pdf`, flags milestones at risk.
- `/rfi-followup` -> reads `9.Operational/Registers/RFI_Register.md`,
  surfaces open RFIs aging past 5 business days.

## Voice Rules

All output for this project follows Your Company voice rules:
- No em-dashes. Hyphens or periods only.
- No supplier names on client documents.
- No PEMB or Red Dot Buildings language.
- No [FORBIDDEN PROJECT].
- Deck always in scope.
- Engineering costs folded into fab/erection rates.

## Bid Rates (Q2 2026 - CEO-locked)

Do not modify these values. They come from bridge/bid_rates.py.

- Fabrication: $3,750/ton
- Erection: $970/ton
- Joists: $4,500/ton
- Roof deck: $[ROOF DECK RATE]/SF
- Composite deck: $[COMPOSITE DECK RATE]/SF
- Anchor bolts: $[ANCHOR RATE]/each
- G&A: 7.5%

## Notes

{{NOTES}}
