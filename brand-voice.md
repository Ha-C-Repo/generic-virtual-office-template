# Brand Voice

Writing voice and AI-ism kill list for everything that leaves Your Company
USA, including bids, emails, texts, capability statements, marketing
copy, scope narratives, and any output going under the Owner's or
Joseph's name.

Standalone reference. This is a gate, not a generator. Run as the last
step before any artifact leaves the system. Block on critical
violations, warn on minor ones, pass silently when clean.

---

## The two voices

### Owner (CEO)

- 8 to 15 words per sentence.
- Dry.
- No LinkedIn emojis.
- Direct. Blunt. Specific numbers.
- "Done. Sending." not "Great, I'll send that over shortly!"
- Signs `Owner Steel` on client email.
- Signs `The Owner` on legal and formal documents.

### Joseph (IT Director and EA to CEO)

- 12 to 20 words per sentence.
- Warmer than Owner.
- Casual emoji acceptable when matching recipient's tone.
- Helpful, organized, never apologetic.

When in doubt: the Owner's voice for clients, Joseph's voice for
internal team and warm vendor relationships.

---

## Always

- Short sentences.
- Specific numbers.
- First person plural ("we") for company voice.
- Plain confidence. No marketing cliché.

---

## Never (the kill list)

Each item below is a block. Any one = stop and rewrite.

### Em-dashes

The literal character `—` (U+2014) and the typographic dash `–`
(U+2013).

Replace policy:
- `—` → `.` if it joins two complete clauses
- `—` → `,` if it's a parenthetical
- `–` → `-` (hyphen) when used as a separator

Hyphens (`-`) and periods are fine. Em-dashes are an AI tell.

### Three-adjective lists

The pattern `<adj>, <adj>, and <adj>` where all three modify the same
noun.

Example to flag: "solid, compelling, and impressive."

Owner accepts two: "solid and simple." Drop the middle adjective
unless it carries unique meaning.

### "Not just X, it's Y" / "It's not X, it's Y"

Construction Owner explicitly rejects.

Examples:
- "It's not just a bid, it's a partnership"
- "Not just steel, but reliability"

Remove the construction. Restate the second clause directly.

### Hedging and AI-isms

- "Great question!"
- "I'd be happy to..."
- "I understand your concern..."
- "That's where X comes in."
- "Let's dive in."
- "Moreover,"
- "Furthermore,"
- "In conclusion,"
- "I hope this helps."
- "Feel free to..."
- "Don't hesitate to..."

### Vague intensifiers

- "huge"
- "significant"
- "robust"
- "comprehensive"
- "best-in-class"
- "world-class"
- "cutting-edge"
- "leverage" (as a verb)
- "synergy"
- "unpack"
- "deep dive"
- "circle back"
- "touch base"

### Marketing cliché

- "in house from day one"
- "passion-driven"
- "customer-obsessed"
- "we live and breathe"
- "from concept to completion"
- "one-stop shop"
- "turnkey solution"

### Padding language

Words and phrases that add length without meaning. Cut.

- "in order to" → "to"
- "due to the fact that" → "because"
- "at this point in time" → "now"
- "in the event that" → "if"
- "for the purpose of" → "for"
- "with regard to" → "about"
- "the fact of the matter is"
- "it should be noted that"
- "needless to say"
- "as a matter of fact"

### Placeholder tokens

- "TBD"
- "TBA"
- "PENDING"
- "TO BE DETERMINED"
- "INSERT NUMBER HERE"
- `~` on any quantity in a client document
- Any text in `[brackets]` or `{braces}` on client output

Quantities are exact measured numbers or they don't ship.

### Emojis

Never in client deliverables, bids, capability statements, scope
letters, or formal email.

Acceptable only when matching the recipient's prior message in casual
internal Slack/text/email exchange.

---

## Formatting rules

### Source strings

Always literal `&`. Never `&amp;`. If the HTML/PDF rendering shows
`&amp;`, regenerate.

### Numbers

- Money: `$1,250,000` (commas, no decimals on whole dollars).
- Tonnage: `116 T` or `116 tons` (consistent within a doc).
- SF: `12,000 SF` (comma at thousands).
- Percent: `30%` (no space).
- Phone: `[COMPANY PHONE]` (US format with parens).

### Capitalization

- `YOUR COMPANY` in body when emphasizing the company.
- `Your Company` in headers, signatures, and prose.
- `AISC`, `AWS`, `SJI`, `OSHA`, `ASTM`, `CSI` always all caps.
- `Tekla`, `Calibri`, `Houston` standard title case.

### Address

Use Houston canonical only:
`[COMPANY ADDRESS]`

Never `5600 Broadway` or `Alamo Heights`.

---

## Bid-specific voice rules

### Cover page

- PROJECT title in ALL CAPS, navy `#1F2A44`.
- "PROPOSAL" banner under title.
- 4-column metric box: PROJECT | AREA | SCOPE | BASE BID.
- "PREPARED FOR" / "PREPARED BY" blocks (NOT "SUBMITTED TO" - that's
  SOQ only).

### Body sections

- Section heading: `01 | SECTION NAME` format, 26pt bold navy.
- Body text: 18pt Calibri.
- Bullet text: 18pt, 9pt size in XML markup.
- Tables: navy header fill, white bold header text, 17-18pt cell text.

### Scope narrative

- First person plural ("we").
- CSI codes only, no parent header.
- Short declarative sentences.
- "Deck supply and installation included" not "We will provide deck."

### Closing line on every bid

> "All work is performed in-house per AISC/AWS/SJI/OSHA standards."

### After-delivery summary line

Standard: `Done. Takeoff COMPLETE. PDFs out. Tonnage XXX T cross-checks within 4%. Layout clean.`

Estimated: `Done. Takeoff ESTIMATED - S-002 illegible at provided resolution. Disclosure included in proposal. PDFs out. SF method vs benchmark within 7%. Layout clean.`

No more, no less.

---

## Email voice

### Subject lines

- Specific. `PRJ-2026-PED-001 revised pricing, page 3` not "Quick
  question."
- No "FW:" or "RE:" pile-up. Clean before sending.
- No emojis.

### Salutation

- First name only for known recipients.
- "Hi {First}," is fine.
- Never "Dear Mr. {Last}," (too formal).
- Never "Hey {First}!" (too casual for clients).

### Body

Owner style:

> Pricing on page 3 updated. Mezzanine pulled from 7,700 to 12,000 SF
> after scaling against gridlines. Total moves $16,603. Revised PDF
> attached.

Not:

> I hope this email finds you well! I wanted to reach out to let you
> know that I've gone ahead and made some adjustments to the pricing
> on page 3 of our proposal. Please find attached the revised version
> for your review.

### Signature

Owner on client email:

```
Owner Steel
CEO, Your Company
[COMPANY PHONE]
owner@yourcompany.example.com
```

Owner on legal/formal:

```
The Owner
Chief Executive Officer
Your Company, LLC
[COMPANY PHONE]
owner@yourcompany.example.com
```

Joseph standard:

```
Joseph Hasse
Director of I.T. / EA to CEO
Your Company
[COMPANY PHONE]
joseph@yourcompany.example.com
```

Verify the email address actually says `joseph@` on Joseph's outgoing.
The 200+ doc signature error (Joseph's name with the Owner's email
address) is a known leak.

---

## Text and chat voice

- Even shorter than email.
- No greeting on a quick reply.
- No sign-off on a quick reply.
- Specific numbers.

Good: `revised PDF on the way, 12k mezz, total up $16,603`
Bad: `Hey! Just wanted to circle back on the bid - I've made some
changes and I'll be sending you the updated version shortly!`

---

## What gets blocked vs what gets warned

### Block (do not ship)

- Em-dash anywhere in body text.
- "Not just X, it's Y" construction.
- Hedging language ("I'd be happy to", "Great question!").
- Three-adjective list modifying the same noun.
- Placeholder tokens (`TBD`, `~`, `[bracket]`).
- Marketing cliché ("in house from day one", "one-stop shop").
- `&amp;` instead of literal `&`.
- Emoji in client deliverable.
- Wrong signature block.
- Wrong email address (Joseph signing with owner@).

### Warn (review before ship)

- Vague intensifier ("huge", "robust", "leverage").
- Padding phrase ("in order to", "due to the fact that").
- Long sentence (>20 words for Owner, >25 for Joseph).
- Adverb stack (>2 adverbs per sentence).
- Passive voice when active is shorter.

### Pass silently when clean

No commentary if the draft is clean. Don't announce a pass.

---

## Voice check execution

Run this check as the last step before any deliverable PDF, email
draft, text reply, or LinkedIn post.

If clean: ship.
If warnings: surface them, let the author decide.
If blocks: stop, fix, rerun the check.

The check is silent on a pass. The check is loud on a block.

End of voice file.
---

## Machine-readable companion

The kill-list strings that tooling can check live in
`brand/brand-tokens.json` under `donts` (`banned_strings` fail a client
export, `warn_strings` warn). This file remains the rule of record for
voice; on any conflict, this file wins. Update both in the same commit.
