# Scope Creep Detector

## Triggers

Fire this skill when the user message contains any of:
- "scope creep"
- "scope check"
- "check the scope"
- "scope drift"
- "out of scope"
- "added scope"
- "scope change"
- "bid scope review"

## Purpose

Identify scope items in a takeoff or bid specification that fall outside
Your Company's core structural steel fabrication and erection scope.

Your Company's core scope:
- Structural steel fabrication (W-shapes, HSS, angles, plates, channels)
- Steel joist fabrication and installation
- Metal deck supply and installation (always in scope, never optional)
- Anchor bolt supply and setting (05 05 13)
- Structural steel erection (05 12 00)
- Steel joist erection (05 21 00)
- Steel deck installation - floor and roof (05 31 00, 05 36 00)
- Composite metal decking (05 36 00)
- Shear stud installation

Items that are OUT of Your Company's scope and must be flagged:
- Concrete work (any)
- Masonry
- Mechanical, electrical, plumbing (MEP)
- Roofing membrane or waterproofing
- Architectural metal (railings, stairs are borderline - flag for Owner)
- Pre-engineered metal buildings (PEMB) - never Your Company scope
- Red Dot Buildings or similar manufacturer-specific systems
- General contractor work (earthwork, foundations, landscaping)
- Painting or coating beyond shop primer
- Fireproofing (flag for Owner - may or may not be in scope)

## Output Format

Return a table:

| Line Item | In Scope? | Action |
|-----------|-----------|--------|
| [item]    | Yes / No / Flag for Owner | [note] |

Then a verdict:
- **CLEAN** - no scope creep detected
- **SCOPE ITEMS FLAGGED** - [count] items need review before bid submission
- **HOLD** - do not submit bid until Owner reviews flagged items

## Rules

- Flag fireproofing and architectural metal for Owner - do not auto-reject.
- Metal deck is NEVER optional. If the spec tries to make it optional, flag HOLD.
- Never accept PEMB or Red Dot language without escalating to Owner.
- No em-dashes. Hyphens or periods only.
- Do not fabricate scope decisions. When uncertain, flag for Owner.
