# Steel Reinforcement Takeoffs Made EASY for Beginners! (jrmaDOIESjY)

- URL: https://www.youtube.com/watch?v=jrmaDOIESjY
- Uploader: Tim Fairley
- Duration: 21:49 (1308.7s)
- Frames: 80 @ 0.061 fps (512px), full mode
- Transcript source: captions (537 segments, auto-caption quality with minor garbles)

Thesis: A slide-and-Excel walkthrough that teaches a beginner to quantify rebar by reading structural drawings, then summing measured bar lengths times a standard weight-per-metre (the manual method) or applying a kg-per-cubic-metre ratio to concrete volume (the ratio method), with the recurring warning that laps, starter bars, spacing-to-count, and waste are the things that get missed.

## Chronological walkthrough (with t=MM:SS anchors)

- t=00:01 Intro. Roadmap: basics, terminology, manual takeoff method, ratio method, a worked example, the presenter's Excel template (linked in description), and common mistakes. (frame_0001, presenter to camera.)
- t=00:27 What is a reinforcement takeoff. Quantifying all reinforcement for a project or activity by reviewing structural drawings to determine type, size, length, spacing, and total quantity in tons. (frame_0003.)
- t=00:49 Why do it. Three core reasons: cost estimating (reinforcement supply cost plus labour to install, both driven by total weight); procurement (a schedule of reinforcement sent to a supplier to order against); construction methodology and planning (quantity drives schedule duration, crane lifts, crane type, deliveries, resourcing). (frame_0005, slide "What are they used for?")
- t=01:30 Types of reinforcement. Bar reinforcement (slab, beam, column, footing, starter bars); mesh (SL82, SL92 in slabs and driveways); fabricated items (L-bars, U-bars, custom bends, pre-fab cages dropped into piles); accessories (bar chairs, spacers, tie wire). (frame_0007.)
- t=02:09 Two methodologies. Manual takeoff (measure every bar, multiply by weight per metre; required for procurement and detailed estimates) versus ratio method (standard kg per cubic metre by structure type; for quick estimating). (frame_0009, frame_0011.)
- t=03:13 Units of measurement. Linear metres (ordering bars), number of bars (bars come in pre-fab lengths, typically 3 m or 6 m), weight in kg or tonnes (for estimating, and because reinforcement labour is costed in manhours per ton), area in m2 (for mesh). (frame_0013.)
- t=04:05 Bar sizes terminology. N = normal ductility (500 MPa yield). The number after N = bar diameter in mm. Common sizes N12, N16, N20, N24, N32. Larger bars in columns and beams, smaller in slabs or ligatures. Slide shows a diameter chart: 10, 12, 16, 20, 25, 32 mm. (frame_0016.)
- t=04:50 Spacing notation. "N12-200" or "N12@200" = 12 mm bars at 200 mm centres (c/c). Can be one-way or two-way depending on the plan. On-screen drawing note reads "N16-150 EW TOP" = top layer, east-west, N16 bars at 150 mm spacing. (frame_0018, "SPACING".)
- t=05:29 Lap length. The overlap where two bars meet to maintain structural continuity; needed when one bar is not long enough (slab longer than the pre-fab 3 m or 6 m bar). Always in the general notes. Depends on bar diameter, concrete strength, and bar location (tension vs compression). Rule of thumb 40 to 50 x bar diameter (N16 = 640 to 800 mm). On-screen general-note table is read aloud: N12 lap = 460 mm. (frame_0021, frame_0023.)
- t=06:33 Starter bars. Vertical bars projecting from a slab, footing, or beam to tie in the next concrete pour; specs give embedment length and exposure height. Flagged as commonly missed in takeoffs because of construction joints and additional lap allowances. (frame_0025.)
- t=07:00 Ligatures / ties / stirrups. Smaller diameter (typically N10 or N12) closed loops, around 200 mm, that confine main bars in columns and beams; shown in section views, not plan views. (Narrated; the dedicated slide fell between captured frames.)
- t=07:22 Fabric mesh. Used in rectangular slabs. Common types SL62, SL72, SL82, SL92, SL102. The number is the wire diameter (SL82 = 8 mm bars). Measured in sheets or m2. (frame_0028.)
- t=07:43 Cover. Distance from reinforcement to the outside concrete face; critical for durability and fire protection; affects placement and spacing; always in the general notes (e.g. 40 mm cover to all reinforcement). On-screen cover table shows values such as 80 / 60 / 60 / 45 / 55 mm by exposure condition. (frame_0030.)
- t=08:18 Reinforcement layout drawings. The main and most important drawings. Plan view (bird's-eye) showing position, spacing, direction of rebar in slabs, footings, beams, columns. Worked-slab drawing shown is about 2455 mm long and 920 mm wide with N16-200 both directions. (frame_0032.)
- t=09:00 Section views. A cut through the slab; cross-section side view that clarifies direction and layout, shows the slab sits on another structure, the CJ (construction joint) note, and starter bars coming out of the page around the edges. (frame_0034.)
- t=09:47 Detail drawings. Blow-up views of complex areas: wall-to-slab connections, beam-to-column junctions, penetrations and re-entrant corners, footing details (pads and piers). Cast-in elements like rag bolts or rebar cages. (frame_0037, "FOOTING DETAIL F5".)
- t=10:22 Reinforcement schedule. A tabulated list of all bar types and quantities from a supplier or detailer. Columns shown: BOQ No, Bar Mark, Type and Size, No of Members, No of each, No of total bars required, Shape, Length of each (m), Total length (m). Example rows show Y16 and Y10 bars, an R6 ligature, with bar marks 009 to 030. (frame_0040.)
- t=10:55 General notes. Concrete cover, lap-length rules, minimum bar sizes, placement tolerances all live here and must be read. (Narrated.)
- t=11:11 Manual takeoff process. Four steps: review drawings and specs; set up a quantity takeoff sheet; measure lengths of bars; multiply by weights. (frame_0042, "PROCESS".)
- t=11:44 Worked example begins in Excel. The presenter's template has a master weight-per-metre lookup table by bar type. He lists each bar group as a row: description, name, shape, diameter. The toolbar shows Bluebeam and Copilot add-ins. (frame_0044, frame_0046, frame_0048.)
- t=12:54 X-axis straight bars. N16-200, 2400 mm long (the slab length), standard unit length 6 m so no lap needed. Six bars across the 920-wide-direction span give a total of 14.7 m of N16 and a weight of about 0.02 t (around 20 kg). (frames 0050 to 0058; formula bar in frame_0052 reads =ROUNDUP(K7/(D7/1000)+1,,0), the spacing-to-count formula; frame_0058 shows a weight formula =4*F9/1000.)
- t=14:13 Y-axis straight bars. N16, 920 mm long, 200 spacing, no lap, total 12.88 m.
- t=14:42 U-bars. N16-200 U-bars; width taken as 0.92 + 2 x lap, where N16 standard lap is looked up as 800 mm; two U-bars give about 5 m total length.
- t=15:38 Top and bottom layers. The presenter copies the rows to represent top layer and bottom layer (T and T means two layers), doubling the quantity. Total slab steel comes out to about 0.1 t (100 kg). He notes on camera he forgot the starter bar. (frames 0066 to 0070, filled spreadsheet.)
- t=16:34 Ratio method. Apply standard steel weights per m3 of concrete; based on industry benchmarks, past projects, or current-project data; less accurate but quicker. (frame_0062.)
- t=16:56 Ratio table. Footings 120, Slabs on Ground 120, Suspended Slab 150, Beams 180, Columns 250, Retaining Walls 200 (all kg/m3). (frame_0064.)
- t=17:31 Ratio process. Take overall volume, determine structure type, choose a ratio, multiply. Example: 120 kg/m3 x 100 m3 = 12 tonnes. (frame_0066, "PROCESS".)
- t=17:52 Ratio cross-check against the worked slab. Volume 2.45 x 0.92 x 0.2 (thickness assumed) = about 0.45 m3; at the 120 kg/m3 slab-on-ground ratio that gives about 0.05 t. The manual method gave 0.1 t, so the ratio under-reads by roughly 50 percent. Reverse-engineering the manual answer yields about 240 kg/m3, far above the textbook ratio, meaning this slab is unusually heavily reinforced. (frame_0070; narration t=18:01 to t=19:17.)
- t=19:20 Common mistakes. (frame_0072 section title.)
- t=19:35 Missing lap lengths. Forgetting overlap length; laps common in long slabs, beams, walls; 40 to 50 x bar diameter adds up fast. (frame_0073.)
- t=20:00 Missing starter bars. For walls, columns, future pours; shown in sections or details, not plans; easy to miss in multi-stage construction. (frame_0074.)
- t=20:12 Misreading spacing. The fence-post error: a 1 m slab at 200 mm spacing needs 6 bars, not 5, because you start and finish at the slab edges. Also confusing "@200" as 200 bars, and mis-applying spacing direction or area. (frame_0075, frame_0076 "MISREADING SPACING".)
- t=20:48 (also covered) Missing bars only shown in sections (stirrups, ligatures, additional top bars over supports); always cross-reference plans, sections, and details. (frame_0077.)
- t=21:04 Waste factor. Always apply one; presenter uses 5 percent (slide says typical 3 to 5 percent of total steel weight) for cutting, offcuts, errors, bar bends; omitting it under-orders. (frame_0078, frame_0079.)
- t=21:33 Outro and a teaser to a further estimating video. (frame_0080.)

## The reinforcement takeoff METHOD (step by step)

Manual method (procurement-grade, the one to encode):

1. Read the drawings and general notes first. Establish bar type and size (N notation), spacing, direction (one-way vs two-way), cover, and the lap-length and cover tables from the general notes. Cross-reference plan, section, and detail sheets so section-only bars (ligatures, top bars, starter bars) are not lost.
2. Decompose the element into bar groups. One row per group: straight X bars, straight Y bars, U-bars, L-bars, starter bars, ligatures, mesh. Capture description, mark/name, shape, diameter for each.
3. Count bars from spacing (the load-bearing step). Number of bars across a span = run length divided by spacing, PLUS ONE. The presenter's Excel encodes this as ROUNDUP(span_mm / spacing_mm + 1). The plus-one is the fence-post rule: bars start and finish at the slab edge, so a 1000 mm run at 200 mm spacing is 6 bars, not 5. This is the single most error-prone arithmetic in the video and the explicit "common mistake."
4. Get the length of each bar. For straight bars that equals the element dimension in that axis (minus cover if you are being precise; the video uses the gross dimension). For bent bars (U, L) add the developed length of the legs: the U-bar width in the example is 0.92 m + 2 x lap, with the N16 lap (800 mm) read from the lap rule.
5. Add laps where the element is longer than the stock bar. Stock bars come in 3 m or 6 m. If the run exceeds stock length, add one lap per joint. Lap = the general-note value (e.g. N12 460 mm, N16 630 mm from the on-screen AS3600-style table) or the rule of thumb 40 to 50 x diameter. In the worked slab no run exceeds 6 m, so laps are zero there, but the method explicitly checks this per row.
6. Total length per group = number of bars x length of each (+ laps). Account for top and bottom layers by duplicating the row (the "T and T" two-layer case doubles quantity).
7. Convert length to weight. Total weight = total length (m) x weight per metre (kg/m) for that bar size, from a standard bar-weight table built into the sheet. Stated example in the slides: 100 m of N16 at 1.65 kg/m = 165 kg. The example slab nets about 0.1 t.
8. Apply a waste factor of 3 to 5 percent (presenter uses 5) to the final weight, for cutting, offcuts, bends, and errors. Never omit it or you under-order.
9. Roll up to tonnes for estimating, because reinforcement labour is priced in manhours per ton and supply is priced per ton.

Ratio method (ROM only):

- Volume of concrete (m3) x a steel-density ratio (kg/m3) chosen by element type (table below) = steel weight, then to tonnes. Example 120 kg/m3 x 100 m3 = 12 t.
- The video itself demonstrates the ratio method missing by about 50 percent against the measured method on the same slab (0.05 t vs 0.1 t), and reverse-engineers a true 240 kg/m3 for that slab, so the ratio is a sanity-check or early-ROM tool, never a procurement number.

Spacing-to-count, lap math, weight-per-metre, and the +1 fence-post rule are the four mechanics worth lifting verbatim.

## Is AI involved?

No, this is a manual methodology video. The entire takeoff is done by hand on structural drawings and in a plain Excel template; there is no AI tool, no automated measurement, no machine extraction, and no Claude or LLM use anywhere. Bluebeam (a PDF markup tool, an add-in tab visible in the Excel ribbon) and a Microsoft Copilot button are present in the toolbar (frames 0044 to 0070), but neither is used or mentioned. Method, not automation.

## On-screen tools and any Claude skills

| Tool / artifact | How it appears | Used? |
|---|---|---|
| Microsoft Excel | Primary takeoff sheet; weight-per-metre lookup table, per-bar rows, ROUNDUP count formula, weight conversion (frames 0044 to 0070) | Yes, core |
| Presenter's Excel reinforcement-takeoff template | Linked in video description (not opened in browser on screen) | Yes |
| Bluebeam (Revu) | Add-in tab in the Excel ribbon (frames 0044 to 0070) | Present, not used |
| Microsoft Copilot | "Analyze Data / Copilot" buttons in the ribbon | Present, not used |
| Structural drawings (plan, section, detail, schedule) | Slide screenshots of an AS3600-style set | Read manually |
| Claude / any LLM / AI skill | none | No |

No Claude skills, no AI agents, no MCP tools of any kind.

## Concrete numbers, bar sizes, weights, rates, examples shown

Bar sizes and notation (Australian / AS3600 convention):
- N = normal-ductility steel, 500 MPa yield. Number = diameter in mm. Common: N12, N16, N20, N24, N32. Diameter chart on slide: 10, 12, 16, 20, 25, 32 mm. R6 (round/plain) appears in the schedule as a ligature.
- Weight per metre stated explicitly only for N16: 1.65 kg/m (used in "100 m of N16 = 165 kg"). All other per-metre weights live inside the template's lookup table and are NOT individually legible on screen. Do not assume other values from this video.

Lap-length table read off the general notes (on-screen, frame_0023), values in mm:
- N12 = 460, N16 = 630, N20 = 890, N24 = 1200, N28 = 1530, N32 = 1890.
- Rule of thumb stated: 40 to 50 x bar diameter (N16 = 640 to 800 mm). Note the worked example uses 800 mm for the N16 U-bar lap, which is the rule-of-thumb upper bound, slightly above the 630 mm table value; the two sources differ and the presenter picks the rule-of-thumb number for the example.

Cover table (on-screen, frame_0030), mm by exposure: 80 (cast against soil), 60 (below-ground against forms/blinding), 60 (internal drainage channel / process water), 45 (all other surfaces), 55 (all surfaces) - values legible but condition labels partly cut off; treat as indicative.

Ratio table (kg of steel per m3 of concrete, frame_0064):
- Footings 120, Slabs on Ground 120, Suspended Slab 150, Beams 180, Columns 250, Retaining Walls 200.

Mesh: SL62, SL72, SL82, SL92, SL102; trailing-context number = wire diameter (SL82 = 8 mm). Measured in sheets or m2.

Worked slab example: about 2455 mm long x 920 mm wide, N16-200 both directions, top and bottom layers, plus N16-200 U-bars and L starter bars; stock bar 6 m, no laps. Results: X-axis 6 bars, 14.7 m, about 0.02 t; Y-axis 12.88 m; U-bars about 5 m; total about 0.1 t (100 kg). Ratio cross-check at 120 kg/m3 gave about 0.05 t on roughly 0.45 m3, under by about 50 percent; back-calculated true density about 240 kg/m3.

Waste factor: 3 to 5 percent of total steel weight (presenter uses 5).

Stock bar lengths: 3 m and 6 m typical.

## Applicability to a structural steel fabricator (Your Company)

What transfers directly:
- The bar-group decomposition and the "one row per bar mark, count x length x weight-per-metre, then sum to tons" loop is exactly our secondary-steel (rebar/reinforcement) takeoff. When Your Company carries rebar as secondary steel, this is the encodable method: read schedule, count, length, weight, waste, tonnage.
- Reading a reinforcement schedule maps onto our existing schedule-reading work. The schedule columns he shows (Bar Mark, Type and Size, No of Members, No of each, No of total bars, Shape, Length of each, Total length) are structurally identical to the kind of member schedule our A1 schedule-QTY reader on the count-gap branch (feature/count-gap-sf-a1, 37fc34d) parses. The bar mark is the join key the same way a piece mark / section mark is for structural steel. The A1 reader pattern (read QTY from a schedule rather than counting pixels) is the right tool here; rebar schedules are even more tabular than steel framing plans.
- The spacing-to-count + fence-post (+1) rule is a clean, deterministic geometry routine that belongs alongside the Engine B grid-geometry SF logic on the count-gap branch. Number of bars = ROUNDUP(span/spacing) + 1 is precisely the kind of count-gap closure (deriving a count where the drawing gives spacing, not an explicit quantity) that branch exists to do. This is the single most reusable algorithm in the video.
- Lap and waste allowances map to our length-uplift and contingency logic. Laps are a length adder driven by a code table (40 to 50 x dia); waste is a flat 3 to 5 percent on weight. Both are the rebar analogue of detailing/cutting allowances and should be explicit, tagged line items, not buried.
- The confidence posture matches our governance. His ratio method is explicitly ROM and self-admittedly off by 50 percent; that is our LOW-confidence, ROM-only, carry-a-contingency, send-an-RFI tier. The manual measured method is the bid-grade path, exactly our "measured member takeoff beats SF x psf" principle from the SF_AND_ACCURACY standard. His "starter bars and section-only bars get missed" warning is our drawing-completeness gate and our cross-reference-every-sheet discipline.

Where our authoritative data must stay in control (do NOT import his numbers into the steel side):
- Weight-per-metre values. He cites N16 = 1.65 kg/m and hides the rest in a spreadsheet. For STRUCTURAL steel members (W/HSS/angle/channel/plate) the authority is bridge/aisc_validator.py wrapping the 2,299-shape v16.0 database, and nothing in this video touches AISC shapes. For REBAR, if we encode a rebar weight table at all, it must be a separate, sourced, validated table (ASTM A615 #3 to #11 bar weights, or metric N-bar masses), never the single legible 1.65 kg/m number from this video and never an LLM-generated figure. Verify, do not generate still applies.
- Bar-size convention is regional. He uses N (AS/NZS 500 MPa) and SL mesh, an Australian convention. US/Houston jobs use imperial #3 to #18 (eighths-of-an-inch) Grade 60 bar and WWR mesh. The notation, lap tables, and weights do not carry over to a US set; only the method does.
- Lap and cover tables are project- and code-specific. His N12=460 / N16=630 table and his cover values come off one drawing's general notes. Our system must read each job's own general notes, not hardcode his table. The 40 to 50 x dia rule of thumb is fine as a fallback flag, not as the priced number.
- Rates. He prices reinforcement labour in manhours per ton; our rebar pricing, if any, is separate from the CEO-locked BID_RATES in bridge/bid_rates.py (fab/erection/joist/deck) and must not be conflated with structural-steel rates.

What does NOT transfer:
- The ratio (kg/m3) method has no structural-steel-frame analogue and is too coarse for any Your Company bid; at most it is an internal smell test for a rebar sub-scope.
- Concrete-volume reasoning, construction-joint and pour-sequencing logic are concrete-trade concerns, not steel fabrication.
- His tools (Excel template, Bluebeam) are not our pipeline; our equivalent is the drawing-analyzer / project-indexer / count-gap engines plus aisc_validator.

Net: lift the method and the spacing-to-count algorithm onto the count-gap branch for rebar/secondary-steel takeoffs; keep all weight, lap, cover, and rate data in our own validated, per-project, US-convention sources.

## Caveats

- Frame sparsity: 80 frames over 21:49 means about one frame every 16 seconds. The dedicated ligatures/ties slide (narrated around t=07:00) fell between captured frames and is reconstructed from the transcript only. Fast cursor actions inside Excel between sampled frames are inferred from the formula bar plus narration, not seen continuously.
- Excel legibility: the template's full column headers and the per-bar weight-lookup table are too small to read field-by-field at 512px. Two formulas are legible (ROUNDUP count, =4*F9/1000 weight conversion); the rest of the cell logic is inferred. The only weight-per-metre value confirmed on screen is N16 = 1.65 kg/m.
- Transcript is auto-captions: numbers spoken fast are occasionally garbled ("2400" vs the drawing's "2455", "002 tons", "045 m cubed", "liatures" for ligatures, "rio cage" for rebar cage). Dimensions above are reconciled against the drawing frames where possible; minor figures (the exact 14.7 / 12.88 / 5 m subtotals) are as spoken and not independently re-derived.
- Cover-table condition labels (frame_0030) are partly cropped; values are legible, labels indicative.
- Lap value conflict noted in the body: the on-screen N16 table says 630 mm but the worked example uses 800 mm (rule-of-thumb). Not an error to fix, just a source difference to be aware of if encoding.
- No fabrication or fabricated weights, no rates in dollars, and no US/imperial bar data appear anywhere; do not infer any.
