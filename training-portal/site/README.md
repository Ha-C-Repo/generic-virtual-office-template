# Your Company - Staff Training Portal

Internal training portal. 30 mastery-gated modules, Supabase auth and
server-side grading, Netlify static hosting at
https://training.yourcompany.example.com

PRIVATE REPO. Training content is confidential. Internal use only.

## How it works

- Trainees self-register with the shared signup code, then work through
  the modules in order. Each module ends with a Final Knowledge Check.
- Grading happens in Postgres (`submit_quiz`, SECURITY DEFINER). The
  browser never sees the answer key and cannot write progress directly.
- The next module unlocks only after the prior module's check is passed.
- Admins (flagged in the `admins` table) see the dashboard at /admin.html.

## Files

- `index.html` - sign in / sign up
- `suite.html` - curriculum hub with per-account progress and locks
- `<module>.html` x30 - lesson content plus the gating check
- `portal.js` - shared auth guard, gate UI, suite decoration
- `config.js` - Supabase project URL + publishable key (browser-safe)
- `quiz-meta.js` - module unlock order (generated)
- `.github/workflows/keepalive.yml` - pings Supabase twice a week so the
  free project never pauses. Needs repo secrets SUPABASE_URL and
  SUPABASE_ANON_KEY; optional SUPABASE_DB_URL enables the backup export.

Note: GitHub disables scheduled workflows after about 60 days without
repo activity. A commit or a manual run of the workflow inside that
window keeps the schedule alive.

## Deploy

Netlify deploys this repo root as a static site. No build step.
DNS: CNAME `training` -> Netlify site, certificate auto-provisioned.
