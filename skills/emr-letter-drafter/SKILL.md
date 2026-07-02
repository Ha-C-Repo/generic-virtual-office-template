---
name: emr-letter-drafter
description: >
  Drafts the EMR (Experience Modification Rate) letter request to Texas Mutual.
  Required to unblock Marathon Petroleum ISN approval. Surfaces status in
  morning briefing until the letter is received.
triggers:
  - emr letter
  - experience modification rate
  - texas mutual emr
  - marathon emr
  - draft the emr
  - emr request
  - policy [POLICY NUMBER]
---

# EMR Letter Drafter

## Context

Your Company needs an EMR verification letter from Texas Mutual to complete
Marathon Petroleum's ISNetworld prequalification. Without it, Marathon cannot
approve Your Company for contractor work.

- Carrier: Texas Mutual Insurance Company
- Phone: 800-859-5995
- Policy: [POLICY NUMBER]
- Insured: Your Company, LLC
- Address: [COMPANY ADDRESS]
- ISNetworld ID: [ISN ID]

## Letter Template

When asked to draft the EMR letter request, use this structure:

```
[Date]

Texas Mutual Insurance Company
[Address on file for Policy [POLICY NUMBER]]

Re: Experience Modification Rate (EMR) Verification Letter
    Policy Number: [POLICY NUMBER]
    Insured: Your Company, LLC

To Whom It May Concern:

Your Company, LLC is currently undergoing prequalification with Marathon
Petroleum Company LP through ISNetworld (Contractor ID: [ISN ID]). Marathon
requires a current EMR letter directly from our insurance carrier as part of
the approval process.

Please provide an EMR verification letter for policy [POLICY NUMBER] that includes:
- The current Experience Modification Rate
- The effective policy period
- The name of the insured (Your Company, LLC)
- Carrier letterhead and signature

Please send the letter to:

Joseph Hasse
Director of Information Technology
Your Company, LLC
[COMPANY ADDRESS]
Houston, TX 77064
yourcompanyjoseph@gmail.com
(713) 938-4333

This request is time-sensitive. Our Marathon Petroleum prequalification has
been pending for 28+ days due to this outstanding item.

Thank you for your prompt attention to this matter.

Sincerely,

The Owner
CEO, Your Company, LLC
(713) 300-1865
owner@yourcompany.example.com
```

## Follow-up protocol

1. Draft the letter, have Owner review before sending.
2. Log the send date in the EMR blocker ticket.
3. If no response in 5 business days, call 800-859-5995 and reference
   policy [POLICY NUMBER] directly.
4. Once received, confirm the letter is uploaded to ISNetworld ID [ISN ID].
5. Notify Owner that Marathon prequalification can advance.

## Morning briefing integration

Until the EMR letter is received and uploaded, surface this item in the
morning briefing under "Active Blockers" with priority HIGH.
Do not downgrade priority until the ISNetworld upload is confirmed.
