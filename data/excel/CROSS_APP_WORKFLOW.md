# Your Company - Cross-App Workflow Guide

Two workflows for daily use between Excel (Claude sidebar) and the Virtual Office.

No VBA macros. No Power Query. No Power Pivot. No =CLAUDE.ASK() formula.
All Claude interaction is via the sidebar chat (Ctrl+Alt+C in Excel or Word).

---

## Workflow A - PDF to Pricing Sheet

**Goal:** Turn a PDF drawing set into a priced bid ready for delivery.

**Tools:** Excel with Claude sidebar, Virtual Office desktop app.

---

### Step 1 - Open the bid drawings

Open the PDF drawing set. This is reference only - you are not pasting it into Excel yet.
Note the drawing stage visible in the title block: IFC, DD, or Budget/SD.

---

### Step 2 - Open your Your Company pricing template in Excel

Open the Excel pricing template. Press Ctrl+Alt+C to open the Claude sidebar.
If this is your first session after setup, check that the sidebar shows the Your Company
instructions (verify by asking Claude: "what are the locked fab rates?"). If rates come
back correct, you are ready.

---

### Step 3 - Paste the member schedule and parse the BOM

Find the member schedule in the drawings (typically on S-series sheets).
Select all text from the schedule and paste it into the Claude sidebar.

Type in the sidebar: "parse this BOM"

Claude returns a structured table:
- Member marks, designations, quantities, lengths, total weights
- Any unknown shapes flagged with "VERIFY" before you price them
- No dollar amounts yet

Copy the output table into your Excel pricing sheet (column A onward).

---

### Step 4 - Enter rates manually

In Excel, enter the unit rates in the rate column using the locked baseline:
- Fab: $3,750/ton
- Erection: $970/ton
- Joists: $4,500/ton
- Roof deck: $[ROOF DECK RATE]/SF
- Composite deck: $[COMPOSITE DECK RATE]/SF
- Anchor rods: $75 each

Apply the drawing-stage adder to quantities (not prices) if needed:
- DD drawings: multiply quantities by 1.05 before pricing
- Budget/SD: multiply quantities by 1.08 before pricing

---

### Step 5 - Validate pricing before sending

Type in the sidebar: "validate pricing"

Claude reads your pricing rows and returns a validation report:
- Rates vs locked baseline (flags any divergence over 3%)
- Payment terms check (confirms 30/20/50)
- GP margin check per line item
- Supplier name scan (should return PASS)
- Deck in scope check (should return PASS)

Fix any FAIL items before proceeding. WARN items surface to Owner for review.

---

### Step 6 - Switch to Word for the proposal narrative (optional)

Open the Your Company proposal template in Microsoft Word. Press Ctrl+Alt+C in Word.
Claude in the Word sidebar can read your Excel sheet's data in the same Office session.

Type in the Word sidebar: "draft scope narrative from the pricing sheet"

Claude reads the Excel data - no copy-paste needed between apps.
The proposal narrative uses the member list and scope items from your Excel sheet.

Review the draft. Apply email-voice and proposal-format skill rules before finalizing.

---

### Step 7 - Generate two PDFs in the Virtual Office

When pricing and narrative are finalized:
1. Switch to the Virtual Office desktop app
2. Run the bid through the bid pipeline (pricing + sanity gates + Virtual Owner review)
3. Output: two PDFs - client proposal + internal GP report (-GP suffix)

Do not deliver the GP report externally.

---

## Workflow B - Bid Package Quality Check

**Goal:** Cross-check a completed pricing spreadsheet against the proposal document.

**Tools:** Excel with Claude sidebar, Word with Claude sidebar (shared cross-app context).

---

### Step 1 - Open the completed pricing spreadsheet in Excel

Open the finalized pricing spreadsheet. Press Ctrl+Alt+C to open the Claude sidebar.

---

### Step 2 - Open the bid proposal in Word

Open the bid proposal .docx in Microsoft Word. Press Ctrl+Alt+C in Word.

Both Claude sidebars are now active. Since March 2026, Claude for Office apps shares
context across open documents in the same Office session. You do not need to switch tabs.

---

### Step 3 - Ask Claude to cross-check tonnage

In the Excel sidebar, type: "does the tonnage in this sheet match the proposal total?"

Claude reads both the Excel spreadsheet and the Word document simultaneously.
It returns a comparison:
- Tonnage from Excel pricing rows
- Tonnage stated in the Word proposal narrative
- Any discrepancy flagged with specific line references

---

### Step 4 - Fix discrepancies

If tonnage does not match:
- In Excel: trace the source row (Claude will identify it)
- In Word: update the narrative figure to match the Excel total, or vice versa
- Confirm which number is the ground truth before editing either document

---

### Step 5 - Run formula audit on flagged cells

If Claude flagged a cell during the cross-check, type in the Excel sidebar:
"audit formulas" or "fix this formula in [cell reference]"

Claude returns findings for each broken formula with the proposed corrected version.
Reply with "apply finding N" or "apply all" to confirm which fixes to apply.

---

### Step 6 - Final validation before delivery

Type in the Excel sidebar: "validate pricing"

Run the full rate validation one more time after any corrections.
Must return CLEAN before PDF generation.

Then run the Virtual Office bid-output-scrubber skill before final delivery:
- Open Virtual Office
- Type: "scrub this bid output" and paste the final text
- Must return PASS on all six output rules

---

## Notes

- Ctrl+Alt+C opens the Claude sidebar in any Office application.
- The sidebar chat is the only integration point. No formulas, no macros.
- Claude does not auto-save changes. You confirm each change explicitly.
- If the sidebar is slow: close other Office applications and reopen. Edge WebView2
  handles the sidebar - restarting Excel clears the context.
- For large BOM tables (over 200 rows): paste in sections of 50 rows to avoid
  sidebar context limits.
