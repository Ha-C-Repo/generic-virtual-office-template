#!/usr/bin/env python3
# Builds the Your Company Shop QC interactive training module (single self-contained HTML).
import base64, io, os
from PIL import Image

SHOTS = "/sessions/zen-sweet-maxwell/mnt/Cowork Virtual Office/ShopQC/training/screenshots"
OUT   = "/sessions/zen-sweet-maxwell/mnt/Cowork Virtual Office/ShopQC/training/YourCo_ShopQC_Training_Module.html"

def datauri(name, maxw=1300):
    p = os.path.join(SHOTS, name + ".png")
    im = Image.open(p).convert("RGB")
    if im.width > maxw:
        h = int(im.height * maxw / im.width)
        im = im.resize((maxw, h), Image.LANCZOS)
    buf = io.BytesIO()
    im.save(buf, format="JPEG", quality=86, optimize=True)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()

IMG = {}
for f in os.listdir(SHOTS):
    if f.endswith(".png") and not f.startswith("_"):
        IMG[f[:-4]] = datauri(f[:-4])

def fig(name, cap, note=None):
    n = f'<p class="note">{note}</p>' if note else ""
    return (f'<figure><img loading="lazy" src="{IMG[name]}" alt="{cap}">'
            f'<figcaption>{cap}</figcaption>{n}</figure>')

def step(num, title, body):
    return (f'<div class="step"><div class="stepnum">{num}</div>'
            f'<div class="stepbody"><h4>{title}</h4>{body}</div></div>')

def quiz(qid, question, options, correct, explain):
    opts = "".join(
        f'<label class="opt"><input type="radio" name="{qid}" value="{i}">'
        f'<span>{o}</span></label>' for i, o in enumerate(options))
    return (f'<div class="quiz" data-correct="{correct}" data-explain="{explain}">'
            f'<p class="q">{question}</p>{opts}'
            f'<button class="check" onclick="checkQuiz(this)">Check answer</button>'
            f'<p class="result"></p></div>')

L = []

L.append(("welcome", "Welcome", "Start here", f"""
<p>This is the hands-on training for <strong>YOUR COMPANY Shop QC v1.0.0</strong>, the
digital execution of quality procedure <strong>NC-QC-FAB-001 Rev 0</strong>. Every
screen and step below was captured from a real walkthrough on a practice project
(<em>DEMO - TRAINING WALKTHROUGH</em>) so what you see is exactly what you will see
on the shop floor.</p>
<p>The program tracks a steel piece from the truck to the trailer through
<strong>three QC gates</strong>, enforcing <strong>six hard blocks</strong> that the
software will not let you bypass. By the end of this module you will be able to
receive material, run a traveler, raise and close an NCR, and release and ship a
piece.</p>
<div class="callout"><strong>How to use this module.</strong> Work top to bottom
using the menu on the left. Each lesson ends with a short knowledge check. Your
progress is saved in this browser, so you can stop and come back. Click any image
to enlarge it.</div>
<div class="grid5">
<div class="card"><span class="big">5</span>tabs / screens</div>
<div class="card"><span class="big">3</span>QC gates</div>
<div class="card"><span class="big">6</span>hard blocks</div>
<div class="card"><span class="big">18</span>traveler fields (structural)</div>
<div class="card"><span class="big">7</span>NCR categories</div>
</div>
{fig("01_projects_overview","The application opens on the Projects tab. Five tabs run left to right: Projects, Receiving (Gate 1), Fabrication (Gate 2), Release (Gate 3), NCR Log.")}
{quiz("w1","How many QC gates does a piece pass through?",["One","Two","Three","Five"],2,"A piece passes Gate 1 (Receiving), Gate 2 (Fabrication), and Gate 3 (Release).")}
"""))

L.append(("concepts", "Core concepts", "Gates, hard blocks, travelers", f"""
<p>Three ideas hold the whole program together. Learn these first and every screen
makes sense.</p>
<h3>The three gates</h3>
<p>A piece moves in one direction through three checkpoints. It cannot skip ahead.</p>
<table class="ref">
<tr><th>Gate</th><th>Tab</th><th>What happens</th><th>Status after</th></tr>
<tr><td>Gate 1</td><td>Receiving</td><td>Material received, MTR and physical checks, QR labels printed, RIR signed</td><td>RECEIVED</td></tr>
<tr><td>Gate 2</td><td>Fabrication</td><td>Floor steps signed in a locked sequence on the traveler</td><td>IN_FAB</td></tr>
<tr><td>Gate 3</td><td>Release</td><td>Completeness re-verified, final sign-off, piece released and shipped</td><td>RELEASED then SHIPPED</td></tr>
</table>
<h3>The traveler</h3>
<p>Every piece carries a <strong>traveler</strong>: a numbered list of QC fields that
must be signed in order. A structural piece has <strong>18 fields</strong>; an SJI
joist has a parallel <strong>20-field</strong> set. Fields 1-4 fill automatically at
receiving. The shop floor signs the middle steps. The last fields are the release
and shipping signatures.</p>
<h3>The six hard blocks</h3>
<p>These are rules the software enforces. You cannot click past them.</p>
<table class="ref">
<tr><th>#</th><th>Hard block</th><th>Where</th></tr>
<tr><td>1</td><td>A CWI name is required to sign a weld-inspection step (no name, no signature)</td><td>Gate 2, fields 8 and 10</td></tr>
<tr><td>2</td><td>Locked sequence: only the lowest unsigned floor step can be signed</td><td>Gate 2</td></tr>
<tr><td>3</td><td>An open NCR puts the piece on NCR HOLD and freezes the whole traveler</td><td>Gate 2 / NCR</td></tr>
<tr><td>4</td><td>Gate 3 requires every field 1-14 signed and zero open NCRs, re-checked at sign time</td><td>Gate 3</td></tr>
<tr><td>5</td><td>CEO co-sign (exact name <em>The Owner</em>) for projects &ge; 50 tons or IAS</td><td>Gate 3</td></tr>
<tr><td>6</td><td>An "Unauthorized field modification" NCR cannot close without an EOR sealed reference</td><td>NCR Log</td></tr>
</table>
<h3>The QR label</h3>
<p>Receiving prints a QR label for every piece. The QR encodes full traceability:
<code>PIECE_ID | PROJECT_NO | HEAT_NO | RECEIVED_DATE</code>. Scanning the label at
Gate 2 or Gate 3 opens that exact piece. A bare piece ID works too.</p>
{quiz("c1","At Gate 2, which step can you sign next?",["Any unsigned step","Only the lowest-numbered unsigned floor step","The highest unsigned step","Whichever the operator chooses"],1,"Hard block 2: the locked sequence only lets you sign the lowest unsigned floor step.")}
{quiz("c2","What freezes an entire traveler until it is resolved?",["A low DFT reading","An open NCR (NCR HOLD)","A missing heat number","A galvanized assembly"],1,"Hard block 3: any open NCR sets the piece to NCR HOLD and freezes the traveler.")}
"""))

L.append(("projects", "Tab 1 - Projects", "Create and track jobs", f"""
<p>The Projects tab is the home screen and the job register. Each row is a project
with live rollup counts: how many pieces are Received, In Fab, Released, and how many
NCRs are still open.</p>
{step(1,"Open the Projects tab and click New Project",
   fig("01_projects_overview","Top row buttons: New Project, Refresh, Project Summary PDF. The grid lists every project with its counts."))}
{step(2,"Fill the project details",
   "Enter the project code, job number, name, GC, contract number, and estimated tonnage. "
   "Tick <strong>IAS inspection required</strong> if the job is IAS. "
   "<span class='hl'>Tonnage matters:</span> a project of 50 tons or more (or any IAS job) "
   "will require the CEO co-sign at Gate 3 (hard block 5)."
   + fig("02_new_project_filled","New Project dialog filled in. This practice job is set to 60 tons, so it will trigger the CEO co-sign later."))}
{step(3,"The project appears in the register",
   fig("03_projects_list_with_demo","The new project shows in the grid with all counts at zero until pieces are received."))}
<p>Select any project and click <strong>Project Summary PDF</strong> to export a one-page
QC status sheet (covered in Reports).</p>
{quiz("p1","Which project field decides whether a CEO co-sign is required at Gate 3?",["GC name","Contract number","Estimated tonnage (and the IAS flag)","Job number"],2,"Tonnage >= 50 OR the IAS flag triggers the CEO co-sign hard block at Gate 3.")}
"""))

L.append(("receiving", "Tab 2 - Receiving (Gate 1)", "Incoming material", f"""
<p>Gate 1 is where steel enters the system. You record the bill of lading (BOL),
capture the mill cert (MTR) values, run the receiving checks, print QR labels, and
sign the Receiving Inspection Report (RIR).</p>
{step(1,"Pick the project and add a BOL line",
   "Select the project at the top, then <strong>Import BOL PDF</strong> to auto-parse a "
   "bill of lading, or <strong>Add Line</strong> to enter one by hand."
   + fig("04_receiving_gate1_overview","The Receiving screen. Right side holds the MTR (Sec 4.1) and Physical (Sec 4.2) checklists. The lower panel is high-strength bolt (fastener) receiving."))}
{step(2,"Enter the section and MTR values",
   "Record the section/mark, BOL quantity, quantity physically received, heat number, "
   "MTR lot number, ASTM grade, and the actual Fy, Fu and CE from the mill cert. "
   "<span class='hl'>The app never invents a value</span> - you record what the MTR says. "
   "If a recorded Fy or Fu is below the ASTM minimum for the grade, the app flags a possible "
   "Material nonconformance for you to act on."
   + fig("05_addline_filled","Add BOL Line: a W14x90, qty 4, heat H-55012, ASTM A992, Fy 52 / Fu 66 ksi (both at or above the A992 minimums of 50 / 65)."))}
{step(3,"The line lands in the grid",
   "Lines parsed from a PDF show a confidence flag; low-confidence lines are highlighted "
   "red and should be reviewed before receiving."
   + fig("06_receiving_line_added","The received line shows quantity, heat, and a confidence of 'manual' for a hand-entered line."))}
{step(4,"Complete both checklists",
   "Tick every item in the <strong>MTR checks (Sec 4.1)</strong> and <strong>Physical "
   "checks (Sec 4.2)</strong> lists. The RIR cannot be signed until all are complete. "
   "Note the on-screen AISC 303-22 straightness reference under the physical checks."
   + fig("07_receiving_checks_ticked","All seven MTR checks and six physical checks ticked.")
   + fig("08_receiving_full_maximized","Maximize the window to see everything at once. The status bar shows the database, storage mode, station, and printer mode."))}
{step(5,"Receive and print labels",
   "Click <strong>Receive + Print Labels</strong>. The app creates one piece per unit "
   "received, seeds each traveler (auto-filling fields 1-4), and prints a QR label per piece. "
   "A quantity mismatch between BOL and received automatically opens a Material nonconformance NCR. "
   "Joist marks (K, KCS, LH, DLH, SLH, G) get the joist traveler; everything else is structural."
   + fig("09_receiving_received_status","After receiving, four pieces (DEMO-W14X90-001 through 004) exist, each with an 18-field structural traveler."))}
{step(6,"Sign the RIR",
   "Click <strong>Sign RIR</strong>, enter the receiving inspector name, and the report is "
   "locked. You can print the RIR PDF immediately."
   + fig("10_sign_rir_dialog","The RIR signature prompt.")
   + fig("12_rir_signed_confirm","RIR signed and locked, with an option to print the RIR PDF."))}
<h3>High-strength bolts (fasteners)</h3>
<p>The lower panel receives RCSC / ASTM F3125 high-strength bolt assemblies. Record the
ROCAP test lot number and verify the bolt, nut and washer markings. Galvanized assemblies
require the lubrication check, and the bolt, nut and washer must share the ROCAP lot number.</p>
{fig("57_add_fastener_lot_dialog","Add Fastener Lot: assembly type, quantity, ROCAP lot, marking and cert verification, galvanized and lubrication checks.")}
{quiz("r1","When can you sign the Receiving Inspection Report (RIR)?",["As soon as a BOL line is added","Only after every MTR and physical check is ticked","Only after Gate 2 is complete","Any time"],1,"All MTR and physical checks must be complete before the RIR can be signed.")}
{quiz("r2","What does a quantity mismatch (BOL vs received) trigger automatically?",["A blocked screen","A Material nonconformance NCR","A reprint","Nothing"],1,"A shortage or overage auto-opens a Material nonconformance NCR.")}
"""))

L.append(("fabrication", "Tab 3 - Fabrication (Gate 2)", "In-process travelers", f"""
<p>Gate 2 is the shop floor. You scan a piece to open its traveler and sign the floor
steps in a locked sequence. This is where hard blocks 1, 2 and 3 live.</p>
{step(1,"Scan a piece to open its traveler",
   "Scan the QR label or type the piece ID. The header shows the piece, section, variant, "
   "heat, status, and progress."
   + fig("14_fabrication_traveler_loaded","Traveler for DEMO-W14X90-001. Fields 1-4 are green (auto-signed by SYSTEM at receiving). Field 5 is the active step. 0/10 floor steps done."))}
{step(2,"Sign the active step",
   "Click <strong>Sign Active Step</strong>. Only the lowest unsigned floor step is "
   "signable (hard block 2). A plain operation step just needs an operator name."
   + fig("15_sign_field5_dialog","Signing field 5 (Cut to length): operator name and optional notes.")
   + fig("16_field5_signed","After signing, status becomes IN_FAB, the progress bar advances, and the next step becomes active."))}
{step(3,"Hard block 1 - the CWI gate at field 8",
   "Field 8 (Pre-weld inspection) requires a Certified Welding Inspector name. Leave it "
   "blank and the app refuses to advance - the weld and all downstream steps are physically "
   "unreachable until a CWI signs."
   + fig("17_cwi_field8_dialog","The field 8 CWI dialog. The CWI name is marked REQUIRED.")
   + fig("18_hardblock_cwi_required","HARD BLOCK: field 8 requires a CWI name. The traveler cannot advance without it.")
   + fig("20_field8_signed_active9","With a CWI name entered, field 8 records PRE-WELD OK and the weld step (9) becomes active."))}
{step(4,"Weld and post-weld steps",
   "Field 9 records the welder ID and the WPS file. Field 10 is the post-weld VT, signed by "
   "a CWI with an ACCEPT / REJECT result. A REJECT prompts you to open an NCR on that step."
   + fig("21_weld_field9_dialog","Field 9: welder ID and WPS selection (pWPS00003 / pWPS00004).")
   + fig("23_postweld_vt_field10","Field 10: post-weld visual test, signed by a CWI with a VT result."))}
{step(5,"Open an NCR on a step (hard block 3)",
   "If something fails, click <strong>Open NCR on Active Step</strong>, choose a category, "
   "describe it, and sign. The piece goes on <strong>NCR HOLD</strong> and the traveler freezes."
   + fig("25_open_ncr_filled","Opening a Welding NCR for a post-weld VT reject.")
   + fig("26_ncr_hold_frozen","NCR HOLD: the header turns red, the unsigned floor steps go red (frozen), and field 18 records the NCR number.")
   + fig("27_ncrhold_sign_blocked","Trying to sign while on hold is blocked: close the NCR on the NCR Log tab first."))}
{step(6,"Finish the floor steps",
   "With the NCR closed, the hold releases and you sign the remaining steps. Some are "
   "optional (mark N/A if not applicable). The dimensional step shows the AISC 303-22 "
   "length tolerance inline; the DFT step captures the coating thickness in mils."
   + fig("41_dimensional_field12_dialog","Field 12 (Dimensional) shows the AISC 303-22 length-tolerance reference while you measure.")
   + fig("44_floor_complete_ready_gate3","All 10 floor steps signed. The header reads 'Floor steps complete - ready for Gate 3'."))}
<p>You can <strong>Reprint Label</strong> or <strong>Print Traveler PDF</strong> at any time
from this tab.</p>
{quiz("f1","Field 8 will not accept a signature unless you provide what?",["A DFT reading","A CWI name","A truck number","The CEO name"],1,"Hard block 1: the pre-weld CWI step requires a CWI name.")}
{quiz("f2","What happens to the traveler when an NCR is opened on the piece?",["Nothing","It is deleted","It freezes on NCR HOLD until the NCR is closed","It jumps to Gate 3"],2,"Hard block 3: an open NCR freezes the whole traveler on NCR HOLD.")}
"""))

L.append(("ncr", "Tab 5 - NCR Log", "Nonconformance lifecycle", f"""
<p>The NCR Log is the register of every nonconformance. You filter by project and status,
raise new NCRs, and disposition or close them. Hard block 6 lives here.</p>
{step(1,"Review the log",
   "Each NCR shows its piece, gate, category, description, status, and disposition. NCRs open "
   "more than 30 days with no disposition are highlighted for CEO review."
   + fig("28_ncr_log_overview","The NCR Log with one open Welding NCR raised from the Gate 2 reject."))}
{step(2,"Disposition and close a standard NCR",
   "Select an NCR, click <strong>Disposition / Close</strong>, choose a disposition "
   "(USE AS IS, REWORK, REPAIR, REJECT/SCRAP), enter the authority, tick <strong>Close this "
   "NCR now</strong>, and sign. Closing the last open NCR on a piece releases its hold."
   + fig("31_ncr_disposition_close_checked","Closing the Welding NCR as REPAIR with the close box ticked.")
   + fig("32_ncr_closed","The NCR is now CLOSED with disposition REPAIR; the piece hold is released."))}
{step(3,"Hard block 6 - EOR reference required",
   "An <strong>Unauthorized field modification</strong> NCR cannot close without an EOR "
   "sealed analysis reference. The disposition dialog even relabels the EOR field to "
   "'REQUIRED for this category'. Try to close it without one and the app blocks you."
   + fig("33_newncr_unauthorized_filled","Raising a new NCR in the 'Unauthorized field modification' category.")
   + fig("36_hardblock6_eor_required","HARD BLOCK: unauthorized field modification NCRs cannot close without an EOR sealed analysis reference.")
   + fig("39_ncr_log_both_closed","With a valid EOR reference supplied, the NCR closes (USE AS IS). Both NCRs are now closed."))}
<p>Use <strong>Export PDF</strong> to produce the full NCR log as a report.</p>
{quiz("n1","Which NCR category cannot be closed without an EOR sealed reference?",["Welding","Dimensional","Unauthorized field modification","Documentation"],2,"Hard block 6 applies to the 'Unauthorized field modification' category.")}
{quiz("n2","What happens when you close the last open NCR on a held piece?",["Nothing","The piece is scrapped","The NCR HOLD is released and fabrication can continue","The piece ships automatically"],2,"Closing the last open NCR releases the hold and returns the piece to IN_FAB.")}
"""))

L.append(("release", "Tab 4 - Release (Gate 3)", "Final release and shipping", f"""
<p>Gate 3 is the final checkpoint and the shipping desk. The piece must pass all
completeness checks, get signed off (with a CEO co-sign on big or IAS jobs), and then be
manifested onto a truck.</p>
{step(1,"Scan the piece to run release checks",
   "The app re-verifies that every field 1-14 is signed and that there are zero open NCRs "
   "(hard block 4). It also tells you if a CEO co-sign is required."
   + fig("46_release_checks_pass_ceo","All checks pass. Because the project is 60 tons, the screen warns that the CEO co-sign is REQUIRED."))}
{step(2,"Hard block 5 - the CEO co-sign",
   "Click <strong>Sign + Release Piece</strong>. Enter the Shop Director and CWI names. On a "
   "qualifying job you must also enter the CEO name <strong>exactly</strong> as "
   "<em>The Owner</em>. Anything else is blocked."
   + fig("47_release_signoff_dialog","The Final Release sign-off: Shop Director, CWI, and (for this job) the CEO name.")
   + fig("49_hardblock5_ceo_required","HARD BLOCK: the entry must read exactly 'The Owner'.")
   + fig("51_released_cert_prompt","With the correct co-sign, the piece is RELEASED and you can print the Final Release Certificate."))}
{step(3,"Build the shipping manifest",
   "In the lower panel, pick the project to list its released pieces. Select the pieces going "
   "on the truck and click <strong>Ship Selected Load</strong>. A piece with any open NCR "
   "cannot ship (the same zero-NCR rule as Gate 3)."
   + fig("53_manifest_released_piece","The released piece appears in the manifest grid, ready to load.")
   + fig("54_ship_load_dialog","Ship load: enter the truck/load number and who shipped it."))}
{step(4,"Confirm the load shipped",
   "Once shipped, the piece status becomes SHIPPED, a manifest PDF is produced, and the piece "
   "leaves the released list."
   + fig("55_shipped_manifest_done","After shipping, the released list is empty - the piece is now SHIPPED and on its manifest."))}
<p>Re-scanning an already-released piece correctly reports "Piece already RELEASED" and the
release button stays disabled.</p>
{quiz("rl1","For a 60-ton project, the CEO co-sign entry must read:",["Any manager name","'M. Owner'","Exactly 'The Owner'","The Shop Director name"],2,"Hard block 5 requires the exact CEO name 'The Owner'.")}
{quiz("rl2","Can a piece with an open NCR be shipped?",["Yes","No - it is blocked, the NCR must be closed first","Only on Fridays","Only if the CEO approves"],1,"The ship gate mirrors the Gate 3 zero-open-NCR rule.")}
"""))

L.append(("reports", "Reports and the dashboard", "PDFs and rollups", f"""
<p>Every stage produces a PDF record, and the Projects tab rolls everything up. During this
walkthrough the app generated five real PDFs:</p>
<table class="ref">
<tr><th>Document</th><th>Where</th><th>What it is</th></tr>
<tr><td>RIR PDF</td><td>Receiving</td><td>Receiving Inspection Report with the signed checklists</td></tr>
<tr><td>Traveler PDF</td><td>Fabrication</td><td>The full signed traveler for a piece</td></tr>
<tr><td>Final Release Certificate</td><td>Release</td><td>The release sign-off certificate per piece</td></tr>
<tr><td>Shipping Manifest</td><td>Release</td><td>The truck load list</td></tr>
<tr><td>Project Summary / QC Summary</td><td>Projects</td><td>One-page project QC status</td></tr>
</table>
<p>The NCR Log also exports the full NCR register as a PDF.</p>
{step(1,"Read the dashboard rollup",
   "The Projects grid shows live counts so you can see a job's status at a glance."
   + fig("56_projects_dashboard_rollup","After the walkthrough: 3 pieces still Received, 0 In Fab, 1 Released (the shipped piece), 0 Open NCRs."))}
{quiz("rp1","How many client-facing PDF types did this walkthrough produce across the gates?",["Two","Three","Five","Ten"],2,"RIR, Traveler, Release Certificate, Manifest, and Project Summary.")}
"""))

L.append(("final", "Final check", "Put it together", f"""
<p>One last set of questions covering the whole flow. Answer all to finish the module, then
mark the lesson complete.</p>
{quiz("q1","Put the gates in order for a single piece.",["Release, Fabrication, Receiving","Receiving (Gate 1), Fabrication (Gate 2), Release (Gate 3)","Fabrication, Receiving, Release","Receiving, Release, Fabrication"],1,"Material is received, fabricated, then released and shipped.")}
{quiz("q2","A joist (SJI) traveler has how many fields versus a structural 18?",["The same 18","20","14","30"],1,"Joists use a parallel 20-field traveler; structural pieces use 18.")}
{quiz("q3","Which two roles must always sign a Gate 3 release (before any CEO co-sign)?",["Welder and operator","Shop Director and CWI","GC and CEO","Receiving inspector and welder"],1,"Final release requires the Shop Director and the CWI names.")}
{quiz("q4","The QR label encodes which four fields?",["Name, date, color, size","Piece ID, project number, heat number, received date","Only the piece ID","Welder, WPS, gate, status"],1,"The QR payload is PIECE_ID | PROJECT_NO | HEAT_NO | RECEIVED_DATE.")}
{quiz("q5","A piece is on NCR HOLD. What must happen before fabrication continues?",["Reprint the label","Close the NCR on the NCR Log tab","Ship it","Lower the tonnage"],1,"The hold only releases when the NCR is closed.")}
<div id="finishbox" class="callout" style="display:none">
<h3>Module complete</h3>
<p>You have covered all five tabs, the three gates, and all six hard blocks of Your Company
Shop QC. Keep the one-page reference handy on the floor, and remember: when the software
blocks you, it is enforcing NC-QC-FAB-001 - find the missing signature, reading, or NCR
rather than working around it.</p></div>
"""))

navhtml = "".join(
    f'<li><a href="#{lid}" data-target="{lid}"><span class="dot" id="dot-{lid}"></span>'
    f'<span class="navtitle">{title}</span><span class="navsub">{sub}</span></a></li>'
    for (lid, title, sub, _b) in L)

sections = "".join(
    f'<section id="{lid}" class="lesson">'
    f'<div class="lessonhead"><h2>{title}</h2>'
    f'<button class="donebtn" onclick="markDone(\'{lid}\')">Mark lesson complete</button></div>'
    f'{body}</section>'
    for (lid, title, sub, body) in L)

ids = [lid for (lid, *_r) in L]

HTML = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Your Company Shop QC - Training Module</title>
<style>
:root{{--ink:#141414;--bg:#f4f4f5;--panel:#fff;--line:#e3e3e6;--red:#b3122b;--green:#1b7a3d;--amber:#caa42a;--muted:#6b6b70;}}
*{{box-sizing:border-box}}
body{{margin:0;font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;color:var(--ink);background:var(--bg);line-height:1.55}}
header.top{{background:#0f0f10;color:#fff;padding:14px 22px;display:flex;align-items:center;gap:14px;position:sticky;top:0;z-index:30;border-bottom:3px solid var(--red)}}
header.top .brand{{font-weight:700;letter-spacing:.5px}}
header.top .ver{{color:#9a9aa0;font-size:13px}}
.progwrap{{margin-left:auto;min-width:240px}}
.progbar{{height:8px;background:#2a2a2c;border-radius:5px;overflow:hidden}}
.progfill{{height:100%;width:0;background:var(--green);transition:width .4s}}
.progtxt{{font-size:12px;color:#bdbdc2;margin-top:3px;text-align:right}}
.layout{{display:flex;align-items:flex-start}}
nav.side{{width:290px;flex:0 0 290px;position:sticky;top:64px;height:calc(100vh - 64px);overflow:auto;background:var(--panel);border-right:1px solid var(--line);padding:10px}}
nav.side ul{{list-style:none;margin:0;padding:0}}
nav.side a{{display:flex;align-items:center;gap:10px;padding:9px 10px;border-radius:8px;text-decoration:none;color:var(--ink)}}
nav.side a:hover{{background:#f0f0f2}}
nav.side a.active{{background:#11121a;color:#fff}}
nav.side a.active .navsub{{color:#b9b9c4}}
.navtitle{{font-weight:600;font-size:14px;display:block}}
.navsub{{font-size:11px;color:var(--muted);display:block}}
nav.side a .navtitle,nav.side a .navsub{{flex:1}}
.dot{{width:11px;height:11px;border-radius:50%;border:2px solid #c7c7cc;flex:0 0 auto}}
.dot.done{{background:var(--green);border-color:var(--green)}}
main{{flex:1;padding:26px 34px;max-width:1020px}}
.lesson{{display:none;animation:fade .25s}}
.lesson.show{{display:block}}
@keyframes fade{{from{{opacity:0;transform:translateY(6px)}}to{{opacity:1}}}}
.lessonhead{{display:flex;align-items:center;gap:16px;border-bottom:2px solid var(--red);padding-bottom:8px;margin-bottom:14px}}
.lessonhead h2{{margin:0;font-size:24px}}
.donebtn{{margin-left:auto;background:#11121a;color:#fff;border:0;padding:8px 14px;border-radius:8px;cursor:pointer;font-size:13px}}
.donebtn.done{{background:var(--green)}}
h3{{margin:22px 0 8px;font-size:18px}}
h4{{margin:0 0 6px;font-size:16px}}
p{{margin:8px 0}}
code{{background:#ececef;padding:2px 6px;border-radius:5px;font-size:13px}}
.hl{{background:#fff3cd;padding:1px 4px;border-radius:4px;font-weight:600}}
.callout{{background:#eef6ff;border:1px solid #cfe3fb;border-left:4px solid #2f6fb3;padding:12px 16px;border-radius:8px;margin:16px 0}}
figure{{margin:14px 0;background:var(--panel);border:1px solid var(--line);border-radius:10px;overflow:hidden}}
figure img{{display:block;width:100%;cursor:zoom-in}}
figcaption{{padding:8px 12px;font-size:13px;color:var(--muted);border-top:1px solid var(--line)}}
.note{{padding:0 12px 10px;font-size:13px;color:var(--amber)}}
.step{{display:flex;gap:14px;margin:18px 0;padding:14px;background:var(--panel);border:1px solid var(--line);border-radius:10px}}
.stepnum{{flex:0 0 34px;height:34px;width:34px;background:var(--red);color:#fff;border-radius:50%;display:flex;align-items:center;justify-content:center;font-weight:700}}
.stepbody{{flex:1}}
table.ref{{width:100%;border-collapse:collapse;margin:12px 0;font-size:14px;background:var(--panel)}}
table.ref th,table.ref td{{border:1px solid var(--line);padding:8px 10px;text-align:left;vertical-align:top}}
table.ref th{{background:#11121a;color:#fff;font-weight:600}}
.grid5{{display:grid;grid-template-columns:repeat(5,1fr);gap:10px;margin:16px 0}}
.card{{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:12px;text-align:center;font-size:12px;color:var(--muted)}}
.card .big{{display:block;font-size:30px;font-weight:800;color:var(--ink)}}
.quiz{{background:var(--panel);border:1px solid var(--line);border-left:4px solid var(--amber);border-radius:8px;padding:14px 16px;margin:16px 0}}
.quiz .q{{font-weight:600;margin:0 0 8px}}
.opt{{display:flex;align-items:center;gap:9px;padding:6px 8px;border-radius:7px;cursor:pointer}}
.opt:hover{{background:#f3f3f5}}
.opt input{{accent-color:var(--red)}}
.check{{margin-top:8px;background:var(--red);color:#fff;border:0;padding:7px 14px;border-radius:7px;cursor:pointer}}
.result{{margin:8px 0 0;font-size:14px;font-weight:600;min-height:0}}
.result.ok{{color:var(--green)}}
.result.bad{{color:var(--red)}}
.lessnav{{display:flex;justify-content:space-between;margin:26px 0 10px}}
.lessnav button{{background:#11121a;color:#fff;border:0;padding:10px 16px;border-radius:8px;cursor:pointer}}
.lessnav button:disabled{{opacity:.35;cursor:default}}
#lightbox{{position:fixed;inset:0;background:rgba(0,0,0,.85);display:none;align-items:center;justify-content:center;z-index:60;cursor:zoom-out}}
#lightbox img{{max-width:95%;max-height:95%}}
@media(max-width:880px){{nav.side{{display:none}}main{{padding:18px}}.grid5{{grid-template-columns:repeat(2,1fr)}}}}
</style></head>
<body>
<header class="top">
<span class="brand">YOUR COMPANY Shop QC</span><span class="ver">v1.0.0 - NC-QC-FAB-001 Rev 0 - Interactive Training</span>
<div class="progwrap"><div class="progbar"><div class="progfill" id="progfill"></div></div>
<div class="progtxt" id="progtxt">0 of {len(L)} lessons complete</div></div>
</header>
<div class="layout">
<nav class="side"><ul>{navhtml}</ul></nav>
<main>
{sections}
<div class="lessnav"><button id="prevBtn" onclick="go(-1)">&larr; Previous</button>
<button id="nextBtn" onclick="go(1)">Next &rarr;</button></div>
</main>
</div>
<div id="lightbox" onclick="this.style.display='none'"><img id="lbimg" src=""></div>
<script>
const IDS={ids};
let cur=0;
const KEY='ncqc_training_done_v1';
function done(){{try{{return JSON.parse(localStorage.getItem(KEY)||'[]')}}catch(e){{return[]}}}}
function saveDone(a){{localStorage.setItem(KEY,JSON.stringify(a))}}
function show(i){{
  cur=Math.max(0,Math.min(IDS.length-1,i));
  document.querySelectorAll('.lesson').forEach(s=>s.classList.remove('show'));
  document.getElementById(IDS[cur]).classList.add('show');
  document.querySelectorAll('nav.side a').forEach(a=>a.classList.toggle('active',a.dataset.target===IDS[cur]));
  document.getElementById('prevBtn').disabled=cur===0;
  document.getElementById('nextBtn').disabled=cur===IDS.length-1;
  window.scrollTo({{top:0,behavior:'smooth'}});
}}
function go(d){{show(cur+d)}}
function markDone(id){{
  let a=done(); if(!a.includes(id)){{a.push(id);saveDone(a)}} render();
  if(cur<IDS.length-1) setTimeout(()=>show(cur+1),250);
}}
function render(){{
  const a=done();
  IDS.forEach(id=>{{const d=document.getElementById('dot-'+id); if(d)d.classList.toggle('done',a.includes(id));}});
  document.querySelectorAll('.donebtn').forEach(b=>{{const id=b.getAttribute('onclick').match(/'([^']+)'/)[1];
    const isd=a.includes(id); b.classList.toggle('done',isd); b.textContent=isd?'Lesson complete \\u2713':'Mark lesson complete';}});
  const pct=Math.round(a.length/IDS.length*100);
  document.getElementById('progfill').style.width=pct+'%';
  document.getElementById('progtxt').textContent=a.length+' of '+IDS.length+' lessons complete';
  const fb=document.getElementById('finishbox'); if(fb)fb.style.display=a.length===IDS.length?'block':'none';
}}
function checkQuiz(btn){{
  const box=btn.closest('.quiz');const sel=box.querySelector('input:checked');
  const res=box.querySelector('.result');
  if(!sel){{res.className='result bad';res.textContent='Pick an answer first.';return;}}
  const ok=sel.value===box.dataset.correct;
  res.className='result '+(ok?'ok':'bad');
  res.textContent=(ok?'Correct. ':'Not quite. ')+box.dataset.explain;
}}
document.querySelectorAll('nav.side a').forEach((a)=>a.addEventListener('click',e=>{{e.preventDefault();show(IDS.indexOf(a.dataset.target));}}));
document.querySelectorAll('figure img').forEach(img=>img.addEventListener('click',()=>{{
  document.getElementById('lbimg').src=img.src;document.getElementById('lightbox').style.display='flex';}}));
render();show(0);
</script>
</body></html>"""

with open(OUT, "w", encoding="utf-8") as f:
    f.write(HTML)
print("WROTE", OUT, round(os.path.getsize(OUT)/1024/1024, 2), "MB")
