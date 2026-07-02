---
name: runway-persistent-driver
description: Persistent autonomous orchestration of a Runway workflow to a finished master video. Manages wave state, scheduled check-ins, timing memory, and failure handling. Never hands off mid-build unless a human-required step is reached.
---

# /runway-persistent-driver

Drive a Runway workflow from kickoff to finished master video without handing
off to Joseph mid-build. Sleep between long generations via scheduled tasks.
Wake up in a fresh context window, advance the wave, schedule the next
check-in.

---

## Inputs

| Input | Default | Purpose |
|---|---|---|
| `workflow_url` | from RUN_STATE.md or 05_workflow_plan.md | Runway canvas to drive |
| `project_folder` | required | `ACTIVE_PROJECTS/<name>/` |
| `run_state_file` | `<project_folder>/RUN_STATE.md` | Persistent state across waking |

---

## On invoke

1. **Read RUN_STATE.md.** If absent, bootstrap from
   `<project_folder>/05_workflow_plan.md` plus the SESSION-RESUME.md if one
   exists. Default DRIVE_MODE = `claude-autonomous`.
2. **Open Runway workflow via Claude in Chrome MCP.** Navigate to
   `workflow_url`. Re-establish `window.__rfStore` reference for DOM scrapes.
3. **For each node in the current wave**: scrape DOM status (`img` element
   present, `video` element present, Run button `disabled` attribute,
   error/success toast). Mark complete in RUN_STATE.md and record
   actual duration via `runway-timing-memory.record()`.
4. **If current wave complete**: advance to the next wave. Click Run on
   next-wave nodes respecting concurrency limits (max 2 video generations;
   audio nodes can fan out). Record `start_time` per node in RUN_STATE.md.
5. **Compute next wake-up time.** Call
   `runway-timing-memory.next_check_at(running_nodes)`. The result is an
   ISO-8601 timestamp = `min(start_time + 1.5 * (mean + stddev))` across
   running nodes.
6. **Create scheduled task** via `mcp__scheduled-tasks__create_scheduled_task`:
   - `fireAt` = the timestamp from step 5.
   - `prompt` = `"Resume the runway-persistent-driver on <project_folder>."`
   - Record the returned `task_id` in RUN_STATE.md.
7. **When final Add Audio output renders**: run QA scrub via Chrome MCP
   (scrub from 0:00 to 0:30, screenshot every ~2s, check for text gibberish,
   silhouette artifacts, clip transitions). If pass: present master file
   path to Joseph with note "Owner approval required before LinkedIn
   upload." If fail: identify the offending clip, re-run its Gen-4.5 node,
   loop.

---

## Wave state machine

Defined per project in `05_workflow_plan.md`. Standard 30-second 6-clip build:

| Wave | Action | Concurrency |
|---|---|---|
| `WAVE_0` | Populate text nodes via `state.updateGenericNodeData()`, save with Ctrl+S | n/a (instantaneous) |
| `WAVE_1` | NBP image generation | pairs of 2 |
| `WAVE_2` | Gen-4.5 video clips | pairs of 2 |
| `WAVE_3` | Text-to-SFX (6 nodes) | all 6 parallel |
| `WAVE_4` | Add SFX To Clip N (6 nodes) | sequential as upstream completes |
| `WAVE_5` | ElevenLabs TTS | n/a (single node) |
| `WAVE_6` | Stitch | n/a (single node) |
| `WAVE_7` | Master Add Audio | n/a (single node) |
| `WAVE_8` | QA scrub + notify Joseph | n/a (Chrome MCP scrub) |

---

## Failure handling

| Symptom | Action |
|---|---|
| "Too many tasks running or pending" toast | Wait 60s, retry. No state change. |
| Node Run button click missed (button still enabled after click) | Retry with 5px offset. |
| Node returns error twice on the same generation | Screenshot, log to RUN_STATE.md under `## Failures`, notify Joseph for that node only. Continue driving the rest of the wave. |
| Page lost / modal blocks canvas | Reload, re-establish `window.__rfStore`, resume from current wave. |
| Two consecutive failures on the same node | Flip DRIVE_MODE to `manual-handoff`. Write SESSION-RESUME.md with full context. Notify Joseph. |
| Runway auth expired | DRIVE_MODE → `manual-handoff`. Notify Joseph for re-auth. |
| Payment required | DRIVE_MODE → `manual-handoff`. Notify Joseph for credit top-up. |

---

## When to flip DRIVE_MODE to manual-handoff

ONLY these conditions:
- Auth expired or re-auth flow triggered
- Payment / credit purchase needed
- Two consecutive failures on the same node
- An approval gate explicitly marked in 05_workflow_plan.md
- Hardware issue (Chrome MCP unreachable, Runway down)

NOT these:
- "The next step is mechanical." Mechanical means Claude does it.
- "Context might run out." Schedule a wake-up; future-Claude reads RUN_STATE.md.
- "Joseph can finish in a few clicks." No. Claude finishes.

---

## DOM scrape patterns

```js
// Has the NBP rendered an image?
document.querySelector(`[data-id="${nodeId}"] img`) !== null

// Has the Gen-4.5 rendered a video?
document.querySelector(`[data-id="${nodeId}"] video`) !== null

// Is the Run button enabled?
!document.querySelector(`[data-id="${nodeId}"] button[aria-label*="Run"]`)
  ?.disabled

// Rate-limit toast visible?
document.querySelector('[role="status"]')
  ?.textContent?.includes('Too many tasks')

// ∞ toggle state for an eligible node
document.querySelector(`[data-id="${nodeId}"] .Switch__SwitchWrapper-kxfoNw input[type="checkbox"]`)
  ?.checked
```

---

## Concurrency rules (hard)

- Max 2 Gen-4.5 nodes running at once. Runway rejects the third.
- Max 6 audio nodes (Text-to-SFX) running in parallel — safe.
- Stitch + Add Audio are single-node steps with no concurrency to manage.
- NBPs in pairs of 2 — also a per-account limit Joseph hit during v1 build.

---

## Output to user (only at terminal states)

- **Master rendered + QA passed**: post the master video file path. Note
  Owner approval required. Stop driving.
- **Master rendered + QA failed**: post the failed clip number, regenerate
  the clip, continue driving (no user output yet).
- **DRIVE_MODE flipped to manual-handoff**: post SESSION-RESUME.md path + the
  specific blocker. Stop driving.

NO progress chatter between waves. The user does not need to hear
"Wave 3 of 8 complete." They will hear from the driver when the master is
ready or when a human is genuinely needed.

---

## Related

- [[runway-timing-memory]] — duration tracker; this driver records into it
  and queries `next_check_at()`.
- [[runway-full-pipeline]] — the upstream orchestrator; calls this driver
  after WAVE_0 populates text and saves.
- [[feedback-runway-persistent-driving]] — the why and the discipline.
- [[feedback-runway-store-edge-validation]] — wire validation gotcha;
  do not delete-and-re-add wires programmatically.
- [[feedback-runway-prompt-reference-mismatch]] — one NBP per distinct subject.
