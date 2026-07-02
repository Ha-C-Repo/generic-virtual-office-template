# SESSION RESUME
## Project: <ProjectName>

## DRIVE_MODE: claude-autonomous

*Only flip to `manual-handoff` if a HUMAN action is genuinely required:*
- *payment / credit purchase*
- *re-auth flow*
- *approval gate explicitly listed in 05_workflow_plan.md*
- *two consecutive failures on the same node*
- *hardware failure (Chrome MCP unreachable, Runway down)*

*If DRIVE_MODE is claude-autonomous, this file should not exist mid-build —
RUN_STATE.md is the persistent state file. SESSION-RESUME.md only appears
when Claude has genuinely run out of agentic capability.*

---

*Live status file. Updated after every Runway generation step.
If Claude crashes mid-build, the next session reads this first
and continues from the row marked "in progress."*

---

## Project metadata

  Workflow URL:    <runway workflow url after first save>
  Workflow name:   <name as saved in Runway>
  Style:           <01 Corporate / 02 Luxury / 03 Documentary / 04 Bold / 05 Product>
  Aspect ratio:    <9:16 / 16:9 / 1:1>
  Clip count:      <e.g. 6>
  Reference count: <e.g. 3>
  Total duration:  <e.g. 30 seconds>
  Style token:     "<token text appended verbatim to every prompt>"

---

## Pre-flight (must all pass before Runway work)

  [ ] 01_brief.md complete and reviewed by Joseph
  [ ] 02_script.md complete, VO word count inside target range
  [ ] 03_shot_list.md complete
  [ ] 04_runway_prompts.md complete, all 16 Anti-AI Laws verified
  [ ] 05_workflow_plan.md complete with credit estimate
  [ ] 06_qa_checklist.md all 20 items pass
  [ ] Owner approval (required before any public release)

---

## Build progress

| Step | Node type | Node id (Runway uuid) | Status | Notes |
|---|---|---|---|---|
| Reference A | Nano Banana Pro | <uuid> | done | <generated image looks on-brand> |
| Reference B | Nano Banana Pro | <uuid> | pending |  |
| Reference C | Nano Banana Pro | <uuid> | pending |  |
| Clip 01 | Gen-4.5 (T+I to Video) | <uuid> | done | 5s, push-in confirmed, ∞ on |
| Clip 02 | Gen-4.5 (T+I to Video) | <uuid> | in progress | wired NBP→FVF, Text→Prompt, ∞ on, Run pressed |
| Clip 03 | Gen-4.5 (T+I to Video) | <uuid> | pending |  |
| Clip 04 | Gen-4.5 (T+I to Video) | <uuid> | pending |  |
| Clip 05 | Gen-4.5 (T+I to Video) | <uuid> | pending |  |
| Clip 06 | Gen-4.5 (T+I to Video) | <uuid> | pending |  |
| Stitch | Stitch | <uuid> | pending | wire clips 01-06 in time order |
| VO TTS | Text to Speech | <uuid> | pending |  |
| Add Audio | Add Audio | <uuid> | pending |  |

---

## Edge ledger (wires created)

| Edge id | Source → Target |
|---|---|
| xy-edge__<srcId>image-<tgtId>start_frame | NBP → Clip 01 FVF |
| xy-edge__<srcId>prompt-<tgtId>text_prompt | Text → Clip 01 Prompt |
| xy-edge__<srcId>image-<tgtId>start_frame | NBP → Clip 02 FVF |
| xy-edge__<srcId>prompt-<tgtId>text_prompt | Text → Clip 02 Prompt |

---

## Credits spent

| Operation | Count | Cost each | Subtotal |
|---|---|---|---|
| NBP image generation | <n> | 4 | <n*4> |
| Gen-4.5 video clip (standard) | <n> | 4 | <n*4> |
| TTS | <n> | ~5 | <n*5> |
| **Total this session** |  |  | <total> |

Account balance at session start: <n>
Account balance now: <n>

---

## Open issues

  i.    <e.g. Reference A lamp came back with green-glass shade, accept or regenerate?>
  ii.   <e.g. Clip 02 First Video Frame wire was tricky, took 3 tries>

---

## Next action

The next concrete action to take when this session resumes.
Be specific: name the node, the wire, or the click.

Example:
"Run Clip 03 individually. Node id `<uuid>`. ∞ already ON. Wait ~80s.
Then verify clip output and queue Clip 04."

---

## Final approval gate

  [ ] All clips passed frame-by-frame scrub
  [ ] Stitch output reviewed
  [ ] Audio mix reviewed
  [ ] Master video exported from Runway
  [ ] Post-production (captions, end card, three-crop) done in editor
  [ ] **The Owner approval** — required before LinkedIn upload
