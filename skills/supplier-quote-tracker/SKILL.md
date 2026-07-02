# Supplier Quote Tracker

## Triggers

Fire this skill when the user message contains any of:
- "supplier quote"
- "vendor quote"
- "quote tracker"
- "track the quote"
- "log the quote"
- "quote comparison"
- "material quote"
- "steel quote"
- "joist quote"
- "deck quote"

## Purpose

Track and compare vendor quotes for structural steel, joists, and metal deck.
Log quotes internally. Never expose supplier names or per-unit costs in any
client-facing output.

Governance Tier 1: Vulcraft, Canam, Nucor, and Ayamsa are internal suppliers.
Their names MUST NOT appear in proposals, GP reports, emails, or any document
sent to a client or GC.

## Quote Input Format

When logging a quote, collect:
- Material type (structural steel / joists / deck / anchor bolts)
- Quantity and unit (tons / pieces / SF / each)
- Unit price (internal only)
- Lead time
- Quote expiration date
- Quote reference number (if provided)

## Internal Log Entry

Each logged quote is stored internally with:
| Field | Value |
|-------|-------|
| Material | [type] |
| Quantity | [qty + unit] |
| Unit Price | [price - INTERNAL ONLY] |
| Total | [computed total - INTERNAL ONLY] |
| Lead Time | [days or weeks] |
| Expiration | [date] |
| Reference | [ref number] |
| Logged | [today's date] |

## Output to User (Internal View)

Show the internal log entry in full when Joseph or Owner requests it.
This view is for internal use only.

## Output - Client-Facing Documents

NEVER include:
- Supplier names (Vulcraft, Canam, Nucor, Ayamsa, or any other vendor)
- Per-unit material costs
- Quote reference numbers
- Lead times (unless specifically required by the RFP)
- Any information that identifies the supply chain

Client-facing cost line items use only:
- "Structural steel fabrication and erection - per Your Company bid"
- "Steel joist supply and installation - per Your Company bid"
- "Metal deck supply and installation - per Your Company bid"

## Rules

- Never output a supplier name in a document flagged as client-facing.
- Never output raw material cost in client-facing documents.
- If asked to include supplier names in a proposal: refuse and explain the rule.
- No em-dashes. Hyphens or periods only.
- Escalate to Owner if a client directly asks for supplier identification.
