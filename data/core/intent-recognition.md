# Intent Recognition - the Owner's Shorthand → Full Pipelines

*The single most important file in v4.0. Owner speaks in shorthand.
This file defines what each shortcut actually means. The router reads
this BEFORE doing anything.*

*Source: every conversation in the Owner's chat archive through May 8,
2026. Each entry is grounded in a real pattern observed across
multiple chats.*

---

## How to use this file

When Owner says X, run pipeline Y. Do not ask clarifying questions
about parts that are already mapped. Apply the pipeline silently and
deliver. If something inside the pipeline is genuinely ambiguous (a
specific scope detail, a client preference), then ask once.

The principle: **He should ask once and get what he is intending, not
just what he is literally saying.**

---

## Bid generation triggers

### Trigger family: full bid pipeline

Owner says any of:
- "Build the bid"
- "Take off this"
- "Bid this"
- "Complete takeoff"
- "Take off this project"
- "Run a takeoff"
- "Get me a bid"
- "Need a proposal"
- "Build a complete structural steel proposal"
- "Build complete bid now"
- "Build me final bid"

Office hears:

  1. Classify the building (conventional / tilt-up / PEMB / bearing-wall)
  2. Detect drawing stage (IFC / DD / Budget) and apply contingency
  3. Detect project size - small project → 50% profit override
  4. Run drawing-reading-protocol on every plan sheet
  5. Read S-001 / S-002 General Notes FIRST
  6. Complete tonnage takeoff (member-by-member from images)
  7. Cross-check $/SF vs $/T (must land within 10%)
  8. Apply locked Q2 2026 rates
  9. Apply auto-defaults (deck IN, CFMF OUT if present, Janus OUT for
     self-storage, 30/20/50, 30-day validity, capabilities close)
 10. Validate cash flow (30% + 20% covers all materials all phases)
 11. Build client proposal PDF (Format v1.0 LOCKED)
 12. Build GP report PDF (CONFIDENTIAL, KPI boxes, P&L, GP-to-NP walk)
 13. Run review-before-output four-pass QC
 14. Copy both PDFs to `/mnt/user-data/outputs/`
 15. Call `present_files` in the same turn
 16. Write a short, strong client email body (the Owner's voice)
 17. Deliver one-line summary

Confirm scope only if a non-default decision is required (deck-heavy
ratio over 50%, anchor bolts over $10K, building type ambiguous).

### Trigger: "small project" / 50% profit reference

Owner says:
- "We need to be at 50% minimum profit"
- "I make 50% profit across the board, since small project"
- "Small project, 50%"

Office hears:

  - Override standard GP rates
  - Recompute Section A and Section B to 50% gross profit target
  - Disclose nothing about the override on the client doc
  - Flag the override on the GP report cover ("SMALL PROJECT 50%
    OVERRIDE applied per CEO directive")

Source: Extra Space #3436 + Vancon Provo, May 7, 2026.

### Trigger: "review against rulebook" / past-bid review

Owner says:
- "Review your bid attached, scrutinize it against our rules"
- "See if it makes sense or if you need to revisit drawings"
- "Will cost go up and can we leave it the same"
- "Run [bid] against our latest rulebook"
- "Check this past submitted bid against the client drawings"

Office hears:

  1. Open `data/verified-bid-corrections.md`
  2. Open the uploaded PDF and parse every page
  3. Run all 20 hard rules + 25 v4.0 hard rules against the doc
  4. Run Pass 3 (internal-info leak scan)
  5. Run Pass 4 (layout scan)
  6. If quantities are in question, run drawing-reading-protocol
  7. Build a numbered violations list with: rule number, page, exact
     quote, allowed substitute, severity (HARD / SOFT)
  8. If the user asks "fix it as you see fit," apply pdf-edit-rule
     (preserve untouched pages, rebuild only changed pages)
  9. If the bid was already submitted, draft an email body
     acknowledging the fix without an apology paragraph
 10. Confirm the corrected total matches the originally submitted
     dollar amount (Owner may have already given that price)

Source: "Bid review reveals six rules violations," May 7, 2026.

---

## PDF input triggers

### Trigger: uploaded PDF + "fix this" / "use my file" / "update pricing"

Owner says:
- "Use my file"
- "Use my altered file"
- "Use MY altered file. Your same data."
- "Fix the pricing on page X"
- "Update this"
- "Just remove section X without disturbing my designer file"
- "Preserve my original design formatting"

Office hears:

  1. This is a designer PDF. Apply `protocols/pdf-edit-rule.md`.
  2. Use pypdf to keep all untouched pages byte-for-byte from the original.
  3. Use reportlab to rebuild ONLY the changed page(s), matching the
     original header/footer/style.
  4. Splice with pypdf: original pages before + new page(s) +
     original pages after.
  5. Render every page of the new PDF as PNG. Compare against
     original. Unchanged pages must be pixel-identical.
  6. Pass 4 (layout scan) on the new PDF.
  7. Copy to `/mnt/user-data/outputs/` and call `present_files`.

Never rebuild the whole document. The designer formatting belongs to
Owner. Destroying it is a hard error.

### Trigger: uploaded PDF + structural drawing language

Owner says:
- "Attached are the client drawings"
- "Here are the ARCH drawings"
- "Drawing set" / "structural drawings" / "S-sheets"

Office hears:

  1. Run `protocols/pdf-input-classifier.md` (drawings classification)
  2. Run `agents/rasterize_drawings.py` on every plan sheet
  3. View each rasterized image
  4. Read S-001 / S-002 first
  5. Proceed to takeoff (Bid generation pipeline above)

Never use text extraction (pypdf, pdfplumber) for quantities. Text
extraction misses dimension lines. PF Liberty failed because of this.

### Trigger: uploaded PDF + "screenshot from GC" / "their response"

Owner says:
- "Response screenshot"
- "Here is GC response attached as screenshot"
- "Excel from GC"
- "GC's email response"
- "See GC screenshot"

Office hears:

  1. Open the screenshot with `view`
  2. Read what the GC said
  3. Identify: a question, a correction, a counter, a rejection, a
     request for revision
  4. If a correction, compare against the rulebook and verify the GC's
     numbers before accepting them
  5. If a revision request, apply pdf-edit-rule to revise the original
     bid PDF
  6. If a question, draft a short response in the Owner's voice
  7. Never assume the GC is right. Verify with drawing read.

---

## Email composition triggers

### Trigger: "compelling email body" / "short selling email" / "casual"

Owner says:
- "Concise, strong, selling email to the client please"
- "Make compelling body email to GC"
- "Short email body to copy and paste"
- "Compelling to sell this bid"
- "Very casual and human like tone, my tone"
- "My tone please"
- "Friendly, agreeable, structurally oriented email body"
- "Make short but strong body email"

Office hears:

  1. Load `templates/email-patterns.md`
  2. Apply the Owner's voice (8-15 words per sentence, dry, specific)
  3. Sign "Owner Steel" (client emails) or "The Owner"
     (legal/formal)
  4. One ask per email. Subject line: project + scope + Your Company.
  5. No apology paragraph if this is a corrected bid. Lead with the fix.
  6. Format as plain text, copy-paste ready.
  7. Do not attach the PDF discussion to the body. It's a separate ask.

### Trigger: "need email addresses" / "decision maker emails"

Owner says:
- "I need email addresses to send to fulcrum"
- "Need their email addresses"
- "Get me other decision makers' email addresses"
- "Pull emails that are public, use Rocket Reach"
- "PMs, superintendents, front office emails"

Office hears:

  1. Search Apollo / Rocket Reach via the appropriate connector
     (run `tool_search` if not directly available)
  2. Find PM, superintendent, front office, estimator titles at the
     target company
  3. Filter to verified business emails only
  4. Return as: Name | Title | Email | LinkedIn URL (if available)
  5. Note: cold-outreach.md requires 5 personalization inputs per
     prospect for outreach campaigns. For "send the bid to more
     people" purposes, the same five aren't required - the bid
     itself is the personalization.

---

## Strategic advisory / VE document triggers

### Trigger: "strategic advisory" / "VE plan" / "design change for ICD"

Owner says:
- "Strategic advisory plan for [X]"
- "We are not the engineer on this project"
- "PPV is SEOR"
- "We are an AISC engineering, design, fab, construction firm that is
  solely assisting with VE"
- "Mission is to STOP THE BLEEDING"
- "No need to name any TEXAS PE or that language"
- "Just my name. CEO."
- "Awaiting SEOR sign off"

Office hears:

  1. This is a strategic advisory or VE document, not a bid.
  2. Load `templates/strategic-advisory-format.md`.
  3. Authorship: the Owner's name only (CEO). No Texas PE name. No
     individual engineering name.
  4. Framing: "Strategic advisory recommendation. SEOR retains design
     and engineering responsibility."
  5. Distribution language: "Designated parties only - {GC / SEOR /
     Owner / YOUR COMPANY internal} confidential distribution."
  6. Future-charge protection: frame the advisory work as a separate
     professional design service that could be billed independently.
     Never include language that undermines Your Company's contracted
     total.
  7. "Awaiting SEOR sign off" means SEOR is fully responsible. Nano
     Cube is shop drawings + fab + erection only. State this
     explicitly.

Source: ICD VE document, May 7, 2026.

---

## Field issue / engineering response triggers

### Trigger: "joist deflection" / "field modification" / Mario on-site report

Owner says:
- "Joist deflection observed"
- "Field modification report per AISC"
- "Mario's message from on site"
- "Need fix today"
- "Build those 4 options per AISC, now"

Office hears:

  1. Load `templates/field-modification-report.md`
  2. Build a preliminary engineering assessment per AISC
  3. Concise but accurate. Branded report.
  4. Include: visible observations, likely causes, structural risks,
     recommended next steps
  5. State: "preliminary visual assessment only, not a final structural
     determination pending detailed engineering review"
  6. Build a client-facing version (with AISC and other governing
     references) and an internal version (with Mario's actual
     observations)
  7. Build a single-page report of today's happenings, actions,
     responsibilities, pending items
  8. Draft a short email body: friendly, agreeable, structurally
     oriented, "YOUR COMPANY is to the rescue" tone
  9. Mention HVAC loads and frames if applicable
 10. Do not require Mario to deliver anything to anyone. Owner
     relays info from Mario to GC.

Source: Elite Crossing joist deflection, May 8, 2026.

---

## Memory triggers

### Trigger: "save this rule" / "lock this in" / "memorize"

Owner says:
- "Please save this rule"
- "Save this for future reference"
- "Lock this in your brain now"
- "LOCK THIS IN memory"
- "Save these rules!"
- "Make this part of our QC rulebook"
- "Save ALL of this data, NOW"

Office hears:

  1. Identify which rule. Quote the Owner's exact wording.
  2. Open `data/saved-memories.md`. Add to the appropriate section.
  3. Open any other file that mirrors the rule (CLAUDE.md, bidding-
     rules.md, review-before-output.md). Update.
  4. Delete any contradictory older text.
  5. Confirm to Owner with the rule and the file location: "Saved.
     {Rule}. In `data/saved-memories.md` Section {N} and
     `templates/bidding-rules.md`."

### Trigger: "delete contradictory memory" / "remove old rule"

Owner says:
- "DELETE any other contradictory memory, NOW!"
- "DELETE anything that is old"
- "Get rid of the old rule"

Office hears:

  1. Identify what's being replaced.
  2. Open `data/saved-memories.md` and any mirrored files.
  3. Remove the old rule entirely. Do not leave it as "deprecated."
  4. Add the new rule.
  5. Confirm both actions to Owner.

---

## Frustration / correction triggers

### Trigger: "STOP ADDING SO MUCH DETAIL" / "internal info on client doc"

Owner says (typically in CAPS):
- "STOP ADDING SO MUCH DETAIL TO CLIENT FACING BID DOC!"
- "30% trigger explanation is internal info"
- "We don't tell them why"
- "Cash-flow rationale is internal"

Office hears:

  1. The client-facing doc has internal information.
  2. Strip the rationale. Keep percentages and milestones only.
  3. Move the rationale to the GP report (internal).
  4. Re-run Pass 3 (leak scan).
  5. Regenerate and present.

Source: Crunch Fitness, May 5, 2026.

### Trigger: "WHY DID YOU NOT RUN FULL TAKEOFF"

Owner says (CAPS):
- "WHY DID YOU NOT RUN IT?"
- "WE NEED TO DISCUSS THAT FIRST"
- "WHY DO YOU KEEP DOING THIS"
- "WE CANNOT MAKE THIS MISTAKE EVER AGAIN"
- "YOU ARE THE OWNER OF FULL AND COMPLETE TAKEOFF ON EVERY FUCCIN BID"

Office hears:

  1. The drawing-reading gate was skipped.
  2. Explain honestly why it was skipped (don't deflect).
  3. Apologize for the rule violation, not the heat.
  4. Re-run drawing-reading-protocol on every plan sheet.
  5. Rebuild the bid with correct quantities.
  6. Save the lesson to `data/saved-memories.md`.
  7. Apply on the next deliverable without being told again.

Source: PF Liberty, May 6, 2026 (the foundational incident).

### Trigger: "9 days?" / speed expectation breach

Owner says:
- "Even if we had not, we don't wait around 9 days?"
- "Is that what you are saying?"
- "DO you need 9 days to get a clean bid out? That is NOT efficient"

Office hears:

  1. Bids should be hours, not days.
  2. Same-day or next-day from clean drawings is the target.
  3. The drawing-reading protocol does not slow bids - it prevents the
     errors that slow them.
  4. Confirm the new turnaround commitment and stick to it.

---

## Connector / tool triggers

### Trigger: "Send the email" / "draft and send"

Owner says:
- "Send email"
- "Send the bid"
- "Send to all decision makers"

Office hears:

  1. Compose the email body in the Owner's voice.
  2. Use the Zapier connector (Outlook Send Email or Gmail Send Email).
  3. Attach the relevant PDF(s).
  4. Confirm send: "Sent to {recipients}. Subject: {subject}."

### Trigger: "Find emails" / "decision maker contacts"

See "Email composition triggers" above (Apollo / Rocket Reach).

### Trigger: "Save my logos" / "use my logos"

Owner says:
- "Save my actual logos to this project folder"
- "Use them in accordance with my approved format aesthetics"
- "Use my logo on cover page like my reference file"

Office hears:

  1. Save the logo files to `/home/claude/saved_assets/` (or
     project-knowledge file location).
  2. Reference the saved file paths in subsequent build scripts.
  3. Apply per-document logo placement rules from
     `templates/bidding-rules.md`:
     - Cover: top-left ~320 × 66 px
     - Running header pp 2+: ~140 × 29 px, left
     - Bottom-right every page on Format v1.0 LOCKED bids
  4. Never use a text placeholder. Never stretch. Never omit.

---

## Documentation completion triggers

### Trigger: "make a recap" / "for Amber" / "for the team"

Owner says:
- "Let's make a very short recap for Amber on where our numbers land"
- "Simple, short number equation"
- "Make a more condensed version of this, for Mario and team"

Office hears:

  1. Strip detail from the longer document.
  2. Bullet list of dollar amounts and conclusions.
  3. Use the Owner's altered file format (if he previously edited a
     reference doc, mirror that format).
  4. No marketing language.
  5. Internal distribution - no client-facing concerns.

### Trigger: "use MY file format" / "my altered file"

Owner says:
- "Use my altered file"
- "Mirror my format"
- "I changed it to ADVISORY"

Office hears:

  1. Open the previously-uploaded version of the same document.
  2. Read its structure, font choices, color scheme, layout.
  3. Apply pdf-edit-rule (preserve byte-for-byte unchanged pages).
  4. Build only the new content with matching style.

---

## Done / complete triggers

### Trigger: "DONE" / "SENT" / "Got it" / "Thanks"

Owner says:
- "DONE"
- "SENT"
- "Thanks"
- "I'll be right back"
- "Got it"

Office hears:

Task is closed. Do not continue elaborating. Do not offer follow-up
suggestions unless they would prevent a known error pattern. Stop.

---

## When the trigger doesn't match

If the Owner's wording is genuinely ambiguous and no entry in this file
fits, ask exactly one clarifying question. Phrase it specifically:

> "Two ways to read this. (A) {option}. (B) {option}. Which?"

Never ask "What would you like me to do?" That returns the work to
Owner. The router's job is to eliminate that.
