# RUN_STATE — <project_name>

## Drive mode: claude-autonomous
## Workflow URL: <runway_workflow_url>
## Last checked: <iso8601>
## Current wave: WAVE_<N>

---

## Wave status

| Wave | Action | Status |
|---|---|---|
| WAVE_0 | Populate text + save | pending |
| WAVE_1 | NBP images | pending |
| WAVE_2 | Gen-4.5 clips | pending |
| WAVE_3 | Text-to-SFX | pending |
| WAVE_4 | Add SFX To Clip N | pending |
| WAVE_5 | TTS | pending |
| WAVE_6 | Stitch | pending |
| WAVE_7 | Master Add Audio | pending |
| WAVE_8 | QA scrub + notify | pending |

(Status values: `pending` | `running` | `done`)

---

## WAVE_1 — NBP images

| Node | Node ID | Start | End | Status |
|---|---|---|---|---|
| NBP_1 | <id> | <ts> | <ts> | pending |
| NBP_2 | <id> | <ts> | <ts> | pending |
| NBP_3 | <id> | <ts> | <ts> | pending |
| NBP_4 | <id> | <ts> | <ts> | pending |
| NBP_5 | <id> | <ts> | <ts> | pending |
| NBP_6 | <id> | <ts> | <ts> | pending |

(Status values: `pending` | `running` | `rendered` | `errored`)

---

## WAVE_2 — Gen-4.5 clips

| Clip | Node ID | Start | End | Status |
|---|---|---|---|---|
| CLIP_1 | <id> | <ts> | <ts> | pending |
| CLIP_2 | <id> | <ts> | <ts> | pending |
| CLIP_3 | <id> | <ts> | <ts> | pending |
| CLIP_4 | <id> | <ts> | <ts> | pending |
| CLIP_5 | <id> | <ts> | <ts> | pending |
| CLIP_6 | <id> | <ts> | <ts> | pending |

---

## WAVE_3 — Text-to-SFX

| SFX | Node ID | Start | End | Status |
|---|---|---|---|---|
| SFX_1 | <id> | <ts> | <ts> | pending |
| SFX_2 | <id> | <ts> | <ts> | pending |
| SFX_3 | <id> | <ts> | <ts> | pending |
| SFX_4 | <id> | <ts> | <ts> | pending |
| SFX_5 | <id> | <ts> | <ts> | pending |
| SFX_6 | <id> | <ts> | <ts> | pending |

---

## WAVE_4 — Add SFX To Clip N

| Merge | Node ID | Start | End | Status |
|---|---|---|---|---|
| ADDSFX_1 | <id> | <ts> | <ts> | pending |
| ADDSFX_2 | <id> | <ts> | <ts> | pending |
| ADDSFX_3 | <id> | <ts> | <ts> | pending |
| ADDSFX_4 | <id> | <ts> | <ts> | pending |
| ADDSFX_5 | <id> | <ts> | <ts> | pending |
| ADDSFX_6 | <id> | <ts> | <ts> | pending |

---

## WAVE_5 — ElevenLabs TTS

| Node | Node ID | Start | End | Status |
|---|---|---|---|---|
| TTS_MASTER | <id> | <ts> | <ts> | pending |

---

## WAVE_6 — Stitch

| Node | Node ID | Start | End | Status |
|---|---|---|---|---|
| STITCH | <id> | <ts> | <ts> | pending |

---

## WAVE_7 — Master Add Audio

| Node | Node ID | Start | End | Status |
|---|---|---|---|---|
| ADDAUDIO_MASTER | <id> | <ts> | <ts> | pending |

---

## WAVE_8 — QA scrub + notify

| Step | Status | Notes |
|---|---|---|
| Scrub 0:00-0:30 | pending | |
| Text gibberish check | pending | |
| Silhouette check | pending | |
| Transition check | pending | |
| Master path posted to Joseph | pending | |

---

## Scheduled task

- Next check-in: <iso8601>
- Task ID: <scheduled-tasks task id>
- Prompt: "Resume the runway-persistent-driver on <project_folder>."

---

## Failures

(Empty unless a node errored twice. Format per entry:
`- 2026-05-25T14:32:11Z  NODE_ID  error_message  screenshot_path`)

---

## Notes

(Free text. Anything future-Claude needs to know that isn't in the wave grid.)
