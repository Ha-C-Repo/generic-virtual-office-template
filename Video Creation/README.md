# VIDEO STUDIO, COWORK PROJECT
## Setup Guide and Folder Map
### Your Company Video Studio

---

## QUICK SETUP (5 minutes)

### Step 1 — Create the folder on your computer
Place this entire `cowork_video_studio/` folder somewhere stable on your
machine (Desktop, Documents, or a dedicated Claude drive). Do not move it
after setup.

### Step 2 — Open Cowork in Claude Desktop
Claude Desktop → Cowork tab → New Project → Use an existing folder →
Select this `cowork_video_studio/` folder → Name it "Video Studio"

### Step 3 — Paste the Folder Instructions
In the project setup screen (or Settings → Cowork → [Video Studio] → Edit
Instructions), paste the full contents of `FOLDER_INSTRUCTIONS.md`.

### Step 4 — Grant folder access
When prompted, select "Always Allow" for this folder so Claude can read
skill files and write project outputs without asking permission each time.

### Step 5 — Test it
Type: "Make me a 30-second ad for Your Company targeting
Houston business owners. Navy and gold color scheme, authoritative tone."

Claude should immediately run the full pipeline: brief → script → shot
list → prompts → workflow plan → QA checklist — all saved to
`ACTIVE_PROJECTS/YourCo_30s_Ad/`

---

## FOLDER STRUCTURE

```
cowork_video_studio/
│
├── FOLDER_INSTRUCTIONS.md     ← Paste this into Cowork Folder Instructions
├── README.md                  ← This file
│
├── SKILLS/                    ← Read-only. Claude reads these every session.
│   ├── VIDEO_STUDIO.md        ← Main production pipeline and role definitions
│   ├── ANTI_AI.md             ← Anti-artifact rules for every Runway prompt
│   ├── RUNWAY.md              ← Full Runway platform operations reference
│   └── CREATIVE_BRIEF.md      ← Brief template (Claude fills this for each job)
│
├── TEMPLATES/                 ← Read-only. Proven structures Claude uses as patterns.
│   ├── 30s_COMMERCIAL.md      ← 30-second ad template (shot list + structure)
│   ├── 15s_PREROLL.md         ← 15-second pre-roll template
│   ├── VERTICAL_REEL.md       ← TikTok/Reels 9:16 template
│   ├── BRAND_FILM_60s.md      ← 60-second brand film template
│   ├── PRODUCT_DEMO.md        ← Product demo video template
│   ├── EXPLAINER.md           ← Explainer video template
│   └── SHORT_FILM.md          ← Short film / movie scene template
│
├── ACTIVE_PROJECTS/           ← Live production work. One subfolder per job.
│   └── [ProjectName]/
│       ├── 01_brief.md
│       ├── 02_script.md
│       ├── 03_shot_list.md
│       ├── 04_runway_prompts.md
│       ├── 05_workflow_plan.md
│       └── 06_qa_checklist.md
│
├── ASSETS/                    ← Brand assets and reference materials
│   ├── brand/
│   │   ├── Your Company/your_company.jpg    ← Your Company logo (intended canonical, currently MISSING)
│   │   └── brand_colors.md               ← Your Company hex codes and usage rules
│   └── reference/
│       └── [moodboard images, reference videos, style references]
│
└── OUTPUTS/                   ← Claude writes final deliverables here.
    └── [ProjectName]/
        ├── brief_FINAL.md
        ├── script_FINAL.md
        ├── shot_list_FINAL.md
        ├── runway_prompts_FINAL.md
        ├── workflow_plan_FINAL.md
        └── qa_APPROVED.md
```

---

## HOW TO START A NEW VIDEO PROJECT

Just describe what you want in plain language. Examples:

**Simple:**
> "Make a 30-second ad for Your Company targeting Houston
> SMB owners in the $1M to $50M revenue band."

**Detailed:**
> "Create a 15-second pre-roll ad for Your Company.
> Audience: founders and CEOs of 50 to 250 person companies in Houston.
> Message: nine years operating in Houston as a working operator, not
> a consultant. Tone: operator to operator, no consultant theater.
> Deliver in 16:9 and 9:16."

**Movie/Narrative:**
> "Create a 90-second short film scene: a Houston SMB owner at dawn,
> reviewing the next quarter's plan in a quiet office. Cinematic,
> documentary style, no dialogue, just ambient morning sound."

**Social Content:**
> "Generate a 4-week LinkedIn video plan for Your Company: 3 videos per week,
> 15 to 30 seconds each, vertical format, owner-operator narrative arc.
> Draft prompts and scripts for all 12 videos."

---

## HOW TO CONTINUE AN EXISTING PROJECT

> "Continue the the 30s Ad project. The shot list is approved — now
> write the Runway prompts."

Claude will read `ACTIVE_PROJECTS/YourCo_30s_Ad/` and pick up from where
it left off.

---

## HOW TO EXECUTE IN RUNWAY

After Claude generates the `05_workflow_plan.md`, two options:

**Option A — Manual execution:**
Open app.runwayml.com, go to Workflows, build the node canvas following
the workflow plan exactly. Claude's prompts go directly into the Text nodes.

**Option B — Claude in Chrome (automated):**
With Claude in Chrome MCP connected:
> "Execute the the 30s Ad workflow plan in Runway. Use the prompts
> from ACTIVE_PROJECTS/YourCo_30s_Ad/04_runway_prompts.md"

Claude will open Runway in Chrome, build the workflow, run it, and
download the outputs.

---

## SCHEDULED TASKS TO SET UP

In Cowork, click "Scheduled" in the left sidebar and create these:

**Weekly Status Check (every Monday, 8am):**
> "Check all folders in ACTIVE_PROJECTS/ for any projects with files older
> than 7 days that haven't been moved to OUTPUTS/. Generate a status report
> and save to OUTPUTS/weekly_status_[date].md"

**Monthly Content Calendar (1st of each month):**
> "Generate a video content calendar for Your Company for
> next month. Include 8 to 12 video concepts across LinkedIn, YouTube,
> and any other approved channels. Each concept needs: title,
> platform, duration, format, brief description, and production tier
> (simple, medium, complex). Save to OUTPUTS/content_calendar_[month_year].md"

---

## PRODUCTION TIERS & TURNAROUND

| Tier | Description | Clips | Credits | Turnaround |
|---|---|---|---|---|
| Rapid | 6-15s social clip | 2-3 | ~75-100 | Same session |
| Standard | 30s commercial | 6 | ~175-250 | 1 session |
| Premium | 60s brand film | 12 | ~330-500 | 2 sessions |
| Feature | 90s+ short film | 18+ | ~600+ | 2-3 sessions |

All estimates use Gen-4.5 Turbo for draft. Budget 1.5× for final pass
using Gen-4.5 full quality + 4K upscale.

---

## APPROVED VIDEO TYPES

This studio handles all of the following without additional setup:

**Commercial & Advertising**
- TV/OTT commercials (6s, 15s, 30s, 60s)
- Social media ads (Facebook, Instagram, LinkedIn, TikTok, YouTube)
- Pre-roll and mid-roll ads
- Product launch videos
- Promotional reels

**Brand & Corporate**
- Brand films and manifestos
- Company culture videos
- Executive thought leadership videos
- Event recaps and highlight reels
- Trade show and conference content

**Product & Sales**
- Product demo videos
- Feature walkthroughs
- Before/after demonstrations
- E-commerce product videos
- Amazon listing videos

**Social & Content**
- TikTok native content
- Instagram Reels
- YouTube Shorts
- LinkedIn video posts
- Story sequences

**Narrative & Creative**
- Short films (up to 5 minutes)
- Narrative commercial films
- Documentary-style content
- Music video sequences
- Title sequences and motion graphics

**Specialized**
- Character dialogue videos (Lip Sync / Character Script to Video)
- Real-time avatar interactions (Runway Characters)
- Motion transfer from performance video (Kling 3.0)
- AI-dubbed multilingual versions (Voice Dubbing)

---

## NOTES FOR JOSEPH / OWNER

- All projects are saved locally to this folder — no cloud sync
- Final deliverables in `OUTPUTS/` are ready to share externally
- Runway execution requires credits in Joseph's existing Runway team account (operational infrastructure for the build operator)
- Current Runway account: Pro plan, ~3,051 credits
- Owner must approve before any video is shared externally
- For urgent requests: tag as "RUSH" in the project name

---

*Your Company Virtual Office Video Studio*
*Maintained by: Joseph Hasse | Approved by: The Owner, Founder and Principal*
