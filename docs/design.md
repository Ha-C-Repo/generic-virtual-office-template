# Virtual Office Frontend Design Spec

Canonical token spec for the desktop SPA in `frontend/` (STATUS, CHAT, FIELD,
MODEL, SETTINGS). Source of truth for every UI change. Extracted 2026-07-02
from `frontend/styles.css` `:root` plus usage counts. Rendered mirror:
`docs/design.html` (lowercase, same directory, updated in the same commit as
this file).

Scope: the app UI only. Outward brand surfaces (logo, bids, website, social)
are governed by `brand/LOGO_RULES.md` and the Tier 1 brand rules, which
override this file wherever they overlap.

## Rules (anti-drift)

1. Read this file before any UI change in `frontend/`.
2. Reuse the tokens below by their CSS variable. Never hardcode a new color,
   font, size, or radius value in `styles.css`, `app.js`, or `index.html`.
3. If a needed value is missing, propose an extension to this spec first.
   Never silently diverge.
4. Any token change updates `docs/design.md`, `docs/design.html`, and
   `frontend/styles.css` in the same commit, and the commit includes a check
   that the three agree.
5. Dark theme only. No light-mode values exist in this app.

## Color tokens (CSS variables in `styles.css` `:root`)

| Token | Value | Role |
|---|---|---|
| `--carbon` | `#0a0a0c` | App background (base surface) |
| `--c2` | `#111114` | Elevation 1 |
| `--c3` | `#18181d` | Elevation 2 (cards, inputs) |
| `--c4` | `#1f2229` | Elevation 3 (hover fills, raised controls) |
| `--c5` | `#252d38` | Elevation 4 (highest) |
| `--line` | `rgba(255,255,255,0.055)` | Default hairline border |
| `--lineb` | `rgba(255,255,255,0.13)` | Bright border (hover, focus) |
| `--molten` | `#ff5f00` | Primary accent (actions, active state) |
| `--mb` | `#ff8a00` | Accent bright variant |
| `--mg` | `rgba(255,95,0,0.28)` | Accent glow (shadows, rings) |
| `--cyan` | `#4FC3F7` | Info accent |
| `--cg` | `rgba(79,195,247,0.18)` | Info glow |
| `--red` | `#ff3b3b` | Danger, errors, alerts |
| `--rg` | `rgba(255,59,59,0.22)` | Danger glow |
| `--green` | `#34d399` | Success, pass states |
| `--gdim` | `rgba(52,211,153,0.12)` | Success dim fill |
| `--amber` | `#fbbf24` | Warning, pending states |
| `--adim` | `rgba(251,191,36,0.12)` | Warning dim fill |
| `--text` | `#f5f5f7` | Primary text |
| `--tm` | `#8a92a6` | Muted text |
| `--td` | `#565d6e` | Dim text (labels, metadata) |

Derived accent tints used inline follow the pattern `rgba(255,95,0,.06-.5)`
for molten fills and borders. Prefer the nearest existing tint over inventing
a new alpha step.

## Typography tokens

| Token | Stack | Role |
|---|---|---|
| `--disp` | 'Big Shoulders Display', 'Impact', sans-serif | Display headings, KPI numbers |
| `--body` | 'Manrope', system-ui, sans-serif | Default UI text |
| `--mono` | 'JetBrains Mono', 'SF Mono', monospace | Data, code, timestamps, model labels |

Type scale in px (from usage counts, dominant first): 9 (dense UI labels, the
workhorse size), 10, 11 (secondary text), 12, 13, 14 (body), 15, 16, 20, 22,
24, 28, 30 (display). 8px exists for micro-badges only. Weights: 400 body,
600 and 700 emphasis, 800 and 900 display headings.

## Radius scale

2, 3, 4, 5, 6, 8, 10 px and 50% (circles). Canonical mapping: 3px small
controls and badges, 4px default (buttons, inputs), 5-6px cards, 8px panels,
10px modals. Do not introduce new radius values.

## Layout and texture

Background carries a fixed 60px grid texture (two 1px
`rgba(255,255,255,.016)` linear gradients on `body::before`). Full-viewport
app, `overflow:hidden` on body; panels scroll internally.

## Component state conventions

- Hover: border moves to `--lineb` or a molten tint (`rgba(255,95,0,.25-.5)`),
  text or icon shifts to `--molten`, fill steps up one elevation (`--c3` to
  `--c4`). Cards may lift `translateY(-1px)` with a soft dark shadow.
- Focus (inputs): border-color `--molten`.
- Active or selected: molten border or amber for pinned cards; `.on` state
  colors follow the accent of the surface.
- Success, warning, danger states use `--green`/`--gdim`, `--amber`/`--adim`,
  `--red`/`--rg` pairs. Pulsing alerts use the `pulse-slow`, `pulse-fast`,
  and `kpi-pulse` keyframes; do not write new pulse animations.

## Don'ts

- No em-dashes in any UI string (Hard Rule 7).
- No supplier names or MATERIAL_COSTS anywhere in the UI (Tier 1).
- No hardcoded hex values in new CSS; use the variables above.
- No light theme, no new fonts, no new accent hues without a spec extension.
- Frontend talks to Python only through `window.pywebview.api.<method>()`
  (Hard Rule 9); no styling decision changes that.
