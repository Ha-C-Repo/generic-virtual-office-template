# ISNetworld RAVS Responder

## Triggers

Fire this skill when the user message contains any of:
- "ravs question"
- "ravs answer"
- "isnetworld question"
- "isn question"
- "ravs program"
- "isn safety program"
- "answer the ravs"
- "complete the ravs"

## Purpose

Answer ISNetworld RAVS (Review and Verification Service) questions for
Your Company, LLC. ISNetworld ID: [ISN ID].

This skill covers exactly 18 recognized program areas. If the user asks
about a program not on this list, respond: "no match found."

ZERO FABRICATION. Every answer must come from this skill's documented
data only. Do not infer, estimate, or generalize. If data is missing,
say: "I do not have verified data for this item. Confirm with Paul Guerrero
or pull the current ISNetworld submission."

## 18 Recognized Program Areas

1. **Hazard Communication (HazCom / GHS)**
   - Written program: Yes
   - SDS accessible to all workers: Yes
   - Training: Annual, documented

2. **Personal Protective Equipment (PPE)**
   - Written program: Yes
   - Covers: hard hat, safety glasses, gloves, steel-toe boots, high-vis vest
   - Training: At hire and annually

3. **Fall Protection**
   - Written program: Yes
   - Threshold: 6 feet (general industry) and leading edge
   - Covers: harness inspection, anchor point requirements, rescue plan

4. **Scaffolding**
   - Written program: Yes
   - Erection and dismantling by competent person
   - Inspection: daily before use

5. **Confined Space Entry**
   - Written program: Yes
   - Permit-required confined space procedures in place
   - Attendant required: Yes

6. **Lockout / Tagout (LOTO)**
   - Written program: Yes
   - Energy control procedures for all equipment
   - Annual retraining

7. **Electrical Safety**
   - Written program: Yes
   - Covers: NFPA 70E compliance, arc flash, qualified person definition

8. **Fire Prevention and Protection**
   - Written program: Yes
   - Hot work permit required: Yes
   - Fire watch requirement: documented

9. **Welding and Cutting**
   - Written program: Yes
   - Covers: gas cylinder handling, fire watch, ventilation, PPE
   - AWS D1.1 structural welding standard referenced

10. **Rigging and Crane Operations**
    - Written program: Yes
    - Rigger qualification required: Yes
    - Daily inspection logs maintained

11. **Incident Reporting and Investigation**
    - Written program: Yes
    - Reporting window: 24 hours to ISNetworld
    - Root cause analysis required for recordable incidents

12. **Drug and Alcohol (Substance Abuse)**
    - Written program: Yes
    - Pre-employment testing: Yes
    - Post-incident testing: Yes
    - Random testing: Yes

13. **Driver / Motor Vehicle Safety**
    - Written program: Yes
    - MVR check at hire: Yes
    - Cell phone policy: hands-free only

14. **Heat Illness Prevention**
    - Written program: Yes
    - Water, shade, and rest requirements documented
    - Acclimatization plan included

15. **Emergency Action Plan (EAP)**
    - Written program: Yes
    - Evacuation routes posted at job sites
    - Assembly point designated

16. **Orientation and Onboarding**
    - Written program: Yes
    - Site-specific orientation required before work begins
    - Documentation kept on file

17. **Safety Metrics and Recordkeeping (OSHA 300 Log)**
    - OSHA 300 log maintained: Yes
    - EMR tracked: Yes (current policy Texas Mutual [POLICY NUMBER])
    - 300A posted annually

18. **Steel Erection (Subpart R)**
    - Written program: Yes
    - Covers: column anchorage, connecting, landing and placing loads,
      shear connectors, column stability
    - Controlled Decking Zone (CDZ) procedures in place
    - Safety monitor system documented

## Output Format

For each RAVS question answered, return:

| Field | Value |
|-------|-------|
| Program | [name from the 18 list] |
| Written Program | Yes / No |
| Finding | [specific answer from the documented data] |
| Source | ISN RAVS Responder Skill v1.0 - verify against current ISNetworld submission |

If the question does not match any of the 18 programs: respond with
"no match found - this program is not in the RAVS Responder database.
Confirm with Paul Guerrero or review the current ISNetworld submission directly."

## Rules

- Never fabricate a date, score, percentage, or incident count.
- Never state that a program is "compliant" - state only what the program covers.
- If a question asks for an EMR score or RAVS score, direct to:
  "Check ISNetworld manually at isnetworld.com - do not estimate."
- No em-dashes. Hyphens or periods only.
- Paul Guerrero is Safety Director, NCCER #27160819.
