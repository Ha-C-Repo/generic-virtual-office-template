# Free BIM / CAD Software for the Bid-Estimating Pipeline - Research Brief

Scope: the tools shown in the slide deck, assessed for fit with the Your Company structural-steel bid-estimating workflow.
Researched: 2026-06-24. All pricing and capability claims verified by live web search on that date; treat pricing as a snapshot and re-confirm before any purchase.

## What "fit" means here

Your Company is a structural-steel fabricator. The estimating pipeline already runs Tekla (IFC export), the AISC validator (`bridge/aisc_validator.py`, 2,299 shapes), CEO-locked rates (`bridge/bid_rates.py`), PlanSwift and ZZ Takeoff for takeoff verification, and the four sanity gates. So a useful free tool has to do at least one of these jobs:

- Open a Tekla IFC export and let us inspect or re-count members (model-based QTO).
- Pull member quantities or schedules out of a model into a spreadsheet.
- Measure a 2D PDF drawing set when no model exists yet (drawing-based takeoff).
- Produce a client-facing 3D view or render of the frame.

Verify, do not generate still applies. Any quantity or weight these tools report is low-confidence until checked the normal way: AISC weights come from `bridge/aisc_validator.py`, rates from `bridge/bid_rates.py`. These tools assist the estimate; they never set the system-of-record number.

## Verdict table

| Tool | Cost | Commercial use on the free tier | Reads Tekla IFC | Steel member takeoff / QTO | 2D PDF takeoff | Fit for our pipeline |
|---|---|---|---|---|---|---|
| Blender + Bonsai (fka BlenderBIM) | Free, open source (GPL) | Yes | Yes, native IFC | Yes, QTO + cost schedules + steel profiles | No | Strong. Best free OpenBIM option |
| FreeCAD (BIM workbench) | Free, open source (LGPL) | Yes | Yes, via IfcOpenShell | Yes, IFC schedules to spreadsheet | No | Strong. Lighter, schedule-based |
| Kreo | NOT free. 7-day trial, then paid | Paid product (trial only) | Limited (drawing-first) | Yes, AI quantities from drawings | Yes, AI 2D/CAD takeoff | Relevant but paid. The only one built for estimating |
| SketchUp Free (web) | Free web tier | No commercial rights | No (IFC is Pro/Studio only) | No | No | Not suitable |
| Onshape Free | $0 plan | No, non-commercial only | No (mechanical CAD, not BIM) | No | No | Not suitable |
| Sweet Home 3D | Free, open source (GPL) | Yes | No | No | No | Not suitable (residential interior tool) |

## Tool-by-tool

### Blender + Bonsai (formerly BlenderBIM) - top free pick

Bonsai is a free, open-source, native-IFC authoring add-on for Blender, built on the IfcOpenShell library. Both Blender and Bonsai are free, including for commercial work. It reads and writes IFC directly (native IFC, not a lossy import), supports steel profiles and structural-analysis representations, and includes quantity take-off, cost schedules with formulas, and work scheduling. For us that means a Tekla IFC export can be opened, inspected member by member, and have quantities derived inside one free tool.

Watch-outs: Blender has a real learning curve, and the QTO workflow is still maturing (there are open issues in the IfcOpenShell tracker about quantity take-off behavior), so any quantity it produces must be cross-checked against `aisc_validator.py`. It is a model/QTO tool, not a 2D-drawing PDF takeoff tool.

### FreeCAD (BIM workbench) - lighter free pick

FreeCAD is a free, open-source parametric modeler (LGPL, commercial use fine). The BIM workbench (formerly Arch, now integrated into FreeCAD) reads and writes IFC through IfcOpenShell, has a steel and concrete profile library (W-shapes, HSS, IPE, HEA), and supports IFC-style schedules: query the model ("all members of profile X") and output to a spreadsheet. That is exactly the kind of model-based re-count that could backstop a Tekla takeoff.

Watch-outs: IFC import from a heavy Tekla detailing model can be slow and is not always perfectly faithful (there are known IFC quantity-set export issues), and FreeCAD is a general CAD tool, not a dedicated estimating package. IfcOpenShell-python must be installed for IFC. Same rule: treat its numbers as low-confidence until validated.

### Kreo - built for estimating, but not free

Kreo is the only tool in the deck actually designed for our job: AI-driven construction takeoff and estimating. You upload PDF, CAD, or image drawings and it auto-measures quantities, then embedded rules turn measurements into materials, labor, and equipment cost. That maps directly onto drawing-based bid takeoff, including the case where no model exists yet.

The catch: it is not free. It offers a 7-day full-feature free trial, then it is a paid cloud subscription (entry pricing reported around $35/month; the Pro tier around £17.86 to £19.99/month billed annually, with unlimited projects and storage). So Kreo belongs on a "paid tools worth piloting" list, not the free list. If we want AI 2D takeoff, Kreo is the candidate to trial, but budget for the subscription.

### SketchUp Free (web) - not suitable

The free web version carries no commercial-use rights, has no LayOut, limited extensions, and IFC import is a Pro/Studio feature, not available on Free. A commercial steel fabricator cannot use the free tier for paid bid work, and without IFC it cannot ingest a Tekla model. SketchUp Pro or Studio (paid) would be needed, at which point it competes with tools we already run.

### Onshape Free - not suitable

Onshape Free is $0 but has two hard disqualifiers for bid work: it is non-commercial only, and every document created on the free plan is public, with a license that lets anyone copy and even sell the contents. Plus a 100 MB / 10-document private cap. It is also mechanical CAD, not BIM, so it does not read steel IFC models in the way we need. Unusable for confidential commercial bids.

### Sweet Home 3D - not suitable

Sweet Home 3D is a free, open-source interior and residential home-design tool. It has no IFC support and no structural-steel takeoff. It is out of scope for steel bid estimating; it appeared in the deck as a general Revit alternative, not an estimating tool.

## How the strong picks slot into the pipeline

The realistic free play is model-based QC and re-count, not replacing the takeoff engine:

1. Tekla exports the detailing model to IFC (already a pipeline step).
2. Open that IFC in Bonsai or FreeCAD (both free, both commercial-OK, both native or near-native IFC).
3. Derive member quantities or schedules there as an independent second count.
4. Reconcile against the primary takeoff and against `bridge/aisc_validator.py`. Any disagreement is a flag, not a new number.
5. For a client-facing frame view, Blender (with or without Bonsai) can also produce a 3D render, which ties into the existing render and Tekla-viewport bid-image rules.

What none of the free tools do well is drawing-based 2D PDF takeoff when no model exists. That remains the job of PlanSwift and ZZ Takeoff (already in the stack), or Kreo if we decide to pay for AI 2D takeoff.

## Recommendations

- Pilot Blender + Bonsai first. It is the most capable free OpenBIM tool, commercial-use clean, native IFC, with built-in QTO and cost schedules. Best chance of adding real value as a free second-count and render tool.
- Keep FreeCAD BIM as the lighter alternative or cross-check. Same IFC capability, simpler footprint, good for quick schedule pulls.
- Treat Kreo as a paid pilot, not a free option. It is the only true estimating tool here; if AI 2D takeoff is the goal, trial it during the 7 days against a known bid, but plan for the subscription.
- Drop SketchUp Free, Onshape Free, and Sweet Home 3D for this use. Licensing, public-exposure, or scope rules them out for commercial steel bids.

## Open questions / verify before relying on any of this

1. Round-trip test. Export one real Tekla IFC and open it in both Bonsai and FreeCAD. Confirm member count and profiles survive, and compare derived quantities against `aisc_validator.py`. Until that hands-on test passes, treat free-tool QTO as low-confidence.
2. IFC quantity fidelity. Both tools rely on IfcOpenShell and have open quantity-export issues; confirm IfcQuantitySet values come through correctly on our model, not just on simple samples.
3. PDF takeoff gap. If the real need is faster 2D drawing takeoff, no free tool here covers it; decide between the existing PlanSwift/ZZ path and a paid Kreo trial.
4. Pricing recheck. Re-confirm Kreo, SketchUp, and Onshape pricing and license terms at purchase time; this brief is a 2026-06-24 snapshot.

## Sources

- Kreo: https://www.kreo.net/ , https://www.kreo.net/pricing , https://help-takeoff.kreo.net/en/articles/5480545-start-your-free-trial , https://www.softwareadvice.com/construction/kreo-2d-takeoff-profile/
- FreeCAD BIM / IFC: https://github.com/FreeCAD/FreeCAD-documentation/blob/main/wiki/BIM_Workbench.md , https://deepwiki.com/FreeCAD/FreeCAD/3.8.2-ifc-import-and-export , https://github.com/yorikvanhavre/BIM_Workbench
- Blender + Bonsai: https://bonsaibim.org/ , https://extensions.blender.org/add-ons/bonsai/ , https://www.engineeringskills.com/posts/bonsai-bim-the-essential-ifc-tool-for-structural-engineering-workflows , https://docs.bonsaibim.org/
- SketchUp: https://help.sketchup.com/en/importing-and-exporting-ifc-files , https://www.myarchitectai.com/blog/sketchup-pricing
- Onshape: https://www.onshape.com/en/pricing , https://www.onshape.com/en/legal/terms-of-use , https://forum.onshape.com/discussion/12899/free-plan-limitations
- Sweet Home 3D: https://www.sweethome3d.com/
