# Initialization Prompt

Copy everything below the line and give it to your AI assistant as the first
message after mounting this project folder.

---

You are taking over a virtual-office template that was cloned from another
company and scrubbed. Your job is to adapt it to MY company before any real
work happens. Do this in order:

1. Read CLAUDE.md, PROJECT_FOLDER_INSTRUCTIONS.md, owner-rules.md,
   company-details.md, and rates-and-pricing.md so you understand the office
   structure and where the placeholders live.

2. Interview me. Ask for, one topic at a time:
   - Legal company name, industry, location, address, phone, email domain
   - The owner/principal: name, role, how they like to communicate
   - The second operator (assistant / IT / ops), if any
   - Our services and units of pricing (per ton, per SF, per hour, per unit)
   - Our locked rates and margins for each service line
   - Payment terms, scope rules (always-in-scope, never-in-scope), forbidden
     items on client documents
   - Compliance IDs we carry (insurance, registrations)

3. Apply my answers everywhere:
   - Replace "Your Company", "YourCo", "Owner", "yourcompany.example.com",
     and every [BRACKETED] placeholder across the markdown files
   - Fill data/core/owner-profile.md from my answers
   - Set real values in bridge/bid_rates.py, rates-and-pricing.md, and
     library/production-rates.yaml
   - Update company-details.md as the facts of record

4. Adapt the procedures: the estimating and bid workflow was written for
   structural steel. Walk me through skills/ and the bid rules in
   owner-rules.md and propose what to keep, rename, or retire for my industry.
   Do not delete anything without my approval.

5. Remind me to put real API keys in the "API Keys/" folder (never commit
   them) and to review .specify/ governance gates.

Ask one question at a time. Do not invent values. When something is unknown,
leave the placeholder and flag it in a TODO list at the end.
