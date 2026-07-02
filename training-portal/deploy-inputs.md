# Your Company Staff Training Portal - Deploy Inputs

Confirmed by Owner 2026-06-09.

- Portal domain: training.yourcompany.example.com
- Hosting: Netlify free tier, deploying from a PRIVATE GitHub repo (reuse existing GitHub account)
- Keep-alive GitHub Action: lives in the same private portal repo (.github/workflows/keepalive.yml)
- Live site: yourcompany.example.com is WordPress on managed WP hosting (nginx, GCP IP 34.174.181.160). NOT GitHub Pages. Staff Training nav link will be added via wp-admin menu edit, gated on the Owner's go. No other WordPress changes.
- Signup code: STEEL2026
- Admins (flagged in admins table after self-registration): owner@yourcompany.example.com, joseph@yourcompany.example.com
- Brand: dark theme, orange accent #ea580c, per live site and training pages
- Curriculum: 30 modules (Owner's Bearing removed, renumbered M01-M30), de-personalized, in training-portal/curriculum/

## Supabase (S2 done 2026-06-09)
- Org: Your Company (free)
- Project: yourco-training, region East US (North Virginia), ref fbvjvbakwsrohbkanqqm
- Project URL: https://fbvjvbakwsrohbkanqqm.supabase.co
- Publishable key: sb_publishable_nyiaGajR0XYGPMyiH_GIwA_88V2jlOA
- Secret key: stays in Supabase, never recorded here
- DB password: auto-generated in UI, not recorded. Owner resets it himself if the optional SUPABASE_DB_URL backup secret is ever wanted.
- "Automatically expose new tables" was turned OFF at creation; schema uses explicit grants.

## Netlify (S8 done 2026-06-09)
- Project: yourco-training (team Your Company, account yourcompanyjoseph@gmail.com)
- Deploys from GitHub: Ha-C-Repo/yourco-training-portal (private), branch main, no build step
- Netlify GitHub App scoped to ONLY that repo
- Netlify URL: https://yourco-training.netlify.app
- Primary domain: training.yourcompany.example.com (GoDaddy CNAME training -> yourco-training.netlify.app, plus subdomain-owner-verification TXT)
- Cert: Let's Encrypt auto-provisioning after successful DNS verification

## Keep-alive (S9/S10 done)
- .github/workflows/keepalive.yml, Mon+Thu 13:10 UTC, manual run #1 passed
- Repo secrets set: SUPABASE_URL, SUPABASE_ANON_KEY (public values)
- Optional SUPABASE_DB_URL (enables pg_dump backup): Owner adds himself after a DB password reset, IPv4 session-pooler string. Keep-alive runs fine without it.
- Note: GitHub disables schedules after ~60 days without repo activity; a commit or manual run resets it.
