"""
Your Company Virtual Office - Hybrid 3D Model Pipeline

PDF Drawing → LOCAL Extraction (pdfplumber + OCR) → AISC Match
→ IF LOCAL FAILS → AI Vision (Gemini) fallback
→ 3D STL with Tagged Members → Weight/Cost Summary → Feeds Bid Estimator

This is a BID PIPELINE STEP - not just a viewer.
Dropping a drawing into the system generates an accurate takeoff.

Pipeline:
  1a. LOCAL: pdfplumber extracts text/tables → regex finds AISC shapes
  1b. LOCAL: If scanned PDF → OCR (EasyOCR/pytesseract) → regex
  1c. FALLBACK: PDF rasterized → Gemini vision extracts members
  2. Each member matched against 342-shape AISC database (LOCAL)
  3. Weight, dimensions, cross-section data pulled from AISC (LOCAL)
  4. STL generated with all members positioned (LOCAL)
  5. Bill of Materials with weights, costs at current bid rates
  6. Feeds into bid_chain step 4 (pricing)
"""

import json, re
from pathlib import Path
from datetime import datetime, timezone

# AISC shape regex - matches W14x82, HSS6x6x1/2, L4x4x3/8, HP12x53, etc.
AISC_PATTERN = re.compile(
    r'\b(?:W|HP|S|M|C|MC|L|HSS|WT|MT|ST|PIPE)\s?\d+(?:\.\d+)?\s?[xX×]\s?\d+(?:\.\d+)?(?:\s?[xX×]\s?\d*(?:/\d+|\.\d+))?(?:\s?[xX×]\s?\d*(?:\.\d+)?)?(?:\b|(?=\s|$|[,;\)]))',
    re.IGNORECASE
)

# Length patterns: 20'-0", 20 FT, 20', etc.
LENGTH_PATTERN = re.compile(
    r"(\d+)\s*['\u2032]\s*-?\s*(\d+)?\s*[\"\u2033]?|(\d+(?:\.\d+)?)\s*(?:ft|FT|feet|FEET|LF|lf)",
    re.IGNORECASE
)


def extract_members_local(pdf_path: str) -> dict:
    """LOCAL extraction: pdfplumber text/tables → AISC regex matching.
    No AI, no API key, no network required. Runs in <2 seconds."""

    # vj: parity-ok (pass 10g classified: dispatcher J=0.14; disjoint shapes)
    pdf_file = Path(pdf_path)
    if not pdf_file.exists():
        return {"ok": False, "error": f"PDF not found: {pdf_path}"}

    members = []
    method_used = "none"

    # Strategy 1: pdfplumber (best for text-based PDFs)
    try:
        import pdfplumber
        method_used = "pdfplumber"
        with pdfplumber.open(str(pdf_file)) as pdf:
            for page_num, page in enumerate(pdf.pages, 1):
                # Extract tables first (member schedules)
                tables = page.extract_tables()
                for table in tables:
                    if not table or len(table) < 2:
                        continue

                    # ── NEW: Detect column headers for structured extraction ──
                    header = table[0]
                    if header:
                        header_upper = [str(h or "").upper().strip() for h in header]
                        # Find column indices for known headers
                        shape_col = next((i for i, h in enumerate(header_upper) if h in ("SHAPE","DESIGNATION","MEMBER","SIZE","SECTION")), None)
                        length_col = next((i for i, h in enumerate(header_upper) if any(k in h for k in ("LENGTH","LEN","LONG","FT"))), None)
                        qty_col = next((i for i, h in enumerate(header_upper) if h in ("QTY","QUANTITY","COUNT","EA","PCS","NO","NUM")), None)
                        mark_col = next((i for i, h in enumerate(header_upper) if h in ("MARK","TAG","ID","PIECE","PC")), None)

                    # If we found a shape column, use structured extraction
                    if shape_col is not None:
                        for row in table[1:]:  # skip header
                            if not row or len(row) <= shape_col:
                                continue
                            cell_text = str(row[shape_col] or "").strip()
                            if not cell_text:
                                continue
                            shapes = AISC_PATTERN.findall(cell_text)
                            if not shapes:
                                continue
                            shape_clean = re.sub(r'\s+', '', shapes[0]).upper()
                            member = {
                                "shape": shape_clean,
                                "page": page_num,
                                "source": "table_structured",
                            }
                            # Length from column position
                            if length_col is not None and len(row) > length_col:
                                try:
                                    val = str(row[length_col] or "").strip()
                                    if val == "-" or not val:
                                        pass
                                    else:
                                        # Parse feet-inches: 40'-0", 22'-6", 30'-0, etc.
                                        ft_in = re.match(r"(\d+)['\u2032][-\s]*(\d*)", val)
                                        if ft_in:
                                            feet = float(ft_in.group(1))
                                            inches = float(ft_in.group(2)) if ft_in.group(2) else 0
                                            member["length_ft"] = feet + inches / 12.0
                                        else:
                                            # Plain number (already in feet)
                                            clean = re.sub(r'[^\d.]', '', val)
                                            if clean:
                                                member["length_ft"] = float(clean)
                                except (ValueError, TypeError):
                                    pass
                            # Qty from column position
                            if qty_col is not None and len(row) > qty_col:
                                try:
                                    val = str(row[qty_col] or "").strip()
                                    val = re.sub(r'[^\d]', '', val)
                                    if val:
                                        member["qty"] = int(val)
                                except (ValueError, TypeError):
                                    member["qty"] = 1
                            else:
                                member["qty"] = 1
                            # Mark from column position
                            if mark_col is not None and len(row) > mark_col:
                                member["mark"] = str(row[mark_col] or "").strip()
                            members.append(member)
                        continue  # Skip regex fallback for this table

                    # ── FALLBACK: No header detected, use regex on joined row text ──
                    for row in table:
                        if not row:
                            continue
                        row_text = " ".join(str(cell or "") for cell in row)
                        shapes = AISC_PATTERN.findall(row_text)
                        for shape in shapes:
                            shape_clean = re.sub(r'\s+', '', shape).upper()
                            member = {
                                "shape": shape_clean,
                                "page": page_num,
                                "source": "table",
                                "raw_row": row_text[:200],
                            }
                            # Try to extract length from same row
                            length_match = LENGTH_PATTERN.search(row_text)
                            if length_match:
                                if length_match.group(3):
                                    member["length_ft"] = float(length_match.group(3))
                                elif length_match.group(1):
                                    ft = int(length_match.group(1))
                                    inches = int(length_match.group(2) or 0)
                                    member["length_ft"] = ft + inches / 12.0
                            # Try to extract quantity
                            qty_match = re.search(r'\b(\d{1,3})\s*(?:EA|ea|PCS|pcs|EACH|each|QTY|qty)\b', row_text)
                            if qty_match:
                                member["qty"] = int(qty_match.group(1))
                            else:
                                member["qty"] = 1
                            members.append(member)

                # Also scan full page text for shapes not in tables
                text = page.extract_text() or ""
                for line in text.split("\n"):
                    line_shapes = AISC_PATTERN.findall(line)
                    for shape in line_shapes:
                        shape_clean = re.sub(r'\s+', '', shape).upper()
                        # Avoid duplicates from table extraction
                        if any(m["shape"] == shape_clean and m["page"] == page_num for m in members):
                            continue
                        member = {
                            "shape": shape_clean,
                            "page": page_num,
                            "source": "text",
                            "qty": 1,
                        }
                        # Extract length from same line (mirrors table-path logic)
                        length_match = LENGTH_PATTERN.search(line)
                        if length_match:
                            if length_match.group(3):
                                member["length_ft"] = float(length_match.group(3))
                            elif length_match.group(1):
                                ft = int(length_match.group(1))
                                inches = int(length_match.group(2) or 0)
                                member["length_ft"] = ft + inches / 12.0
                        # Extract quantity from same line
                        qty_match = re.search(
                            r'\b(\d{1,3})\s*(?:EA|ea|PCS|pcs|EACH|each|QTY|qty)\b', line)
                        if qty_match:
                            member["qty"] = int(qty_match.group(1))
                        members.append(member)
    except ImportError:
        method_used = "pdfplumber_unavailable"
    except Exception as e:
        method_used = f"pdfplumber_error:{str(e)[:100]}"

    # Strategy 2: If pdfplumber found nothing, try OCR (scanned PDF)
    if not members:
        try:
            import easyocr
            method_used = "easyocr"
            # Convert PDF pages to images
            try:
                import fitz  # PyMuPDF
                doc = fitz.open(str(pdf_file))
                reader = easyocr.Reader(['en'], gpu=False)
                for page_num in range(min(len(doc), 10)):  # max 10 pages
                    page = doc[page_num]
                    pix = page.get_pixmap(dpi=200)
                    img_bytes = pix.tobytes("png")
                    results = reader.readtext(img_bytes)
                    for (bbox, text, conf) in results:
                        if conf < 0.3:
                            continue
                        shapes = AISC_PATTERN.findall(text)
                        for shape in shapes:
                            shape_clean = re.sub(r'\s+', '', shape).upper()
                            members.append({
                                "shape": shape_clean,
                                "page": page_num + 1,
                                "source": "ocr",
                                "confidence": round(conf, 2),
                                "qty": 1,
                            })
                doc.close()
            except ImportError:
                method_used = "easyocr_no_pymupdf"
        except ImportError:
            if method_used == "pdfplumber_unavailable":
                method_used = "no_extraction_libs"

    # Deduplicate and aggregate
    shape_counts = {}
    for m in members:
        key = m["shape"]
        if key in shape_counts:
            shape_counts[key]["qty"] += m.get("qty", 1)
            if m.get("length_ft") and not shape_counts[key].get("length_ft"):
                shape_counts[key]["length_ft"] = m["length_ft"]
        else:
            shape_counts[key] = {**m}

    member_list = list(shape_counts.values())

    return {
        "ok": len(member_list) > 0,
        "method": method_used,
        "members_found": len(member_list),
        "members": member_list,
        "pages_scanned": "all",
        "note": "LOCAL extraction - no AI used" if member_list else "No AISC shapes found locally. Use Gemini vision fallback.",
    }


def extract_members_from_pdf(pdf_path: str, api_key: str = "") -> dict:
    """Step 1-2: Extract member schedule from PDF.

    Priority: LOCAL extraction first (pdfplumber + OCR), Gemini vision fallback.
    This means takeoff works OFFLINE for text-based PDFs.
    """

    # ── TRY LOCAL FIRST (no API, no network, <2 seconds) ──
    local_result = extract_members_local(pdf_path)
    if local_result.get("ok") and local_result.get("members_found", 0) >= 3:
        return {
            "ok": True,
            "method": f"local/{local_result['method']}",
            "members": local_result["members"],
            "note": f"Extracted {local_result['members_found']} members locally (no AI used)",
        }

    # ── LOCAL INSUFFICIENT - FALL BACK TO GEMINI VISION ──
    import base64

    if not api_key:
        if local_result.get("members"):
            return local_result  # partial results better than nothing
        return {"error": "Gemini API key required for visual PDF extraction (local found no AISC shapes)"}

    # Read PDF and convert to base64
    pdf_file = Path(pdf_path)
    if not pdf_file.exists():
        return {"error": f"PDF not found: {pdf_path}"}

    pdf_b64 = base64.b64encode(pdf_file.read_bytes()).decode("ascii")

    # Build vision prompt - tells Gemini exactly what to extract
    prompt = """You are a structural steel detailing expert reading construction drawings.

Extract EVERY structural steel member from these drawings into a JSON array.

For each member, provide:
- "mark": the piece mark or member ID (e.g., "C1", "B2", "G1", "W1")
- "shape": the AISC shape designation (e.g., "W14x82", "W12x26", "HSS6x6x1/4", "L4x4x3/8")
- "length_ft": estimated length in feet (from grid spacing or dimensions shown)
- "qty": quantity of this member (count how many identical members appear)
- "grid": grid line location if visible (e.g., "A-1", "B-3")
- "type": member type - one of: "column", "beam", "girder", "brace", "joist", "misc"
- "elevation": if shown, the elevation or level (e.g., "TOC +14'-0\"", "roof")

If a member schedule/table is shown on the drawings, use it directly.
If not, read each member from the framing plans.

Respond with ONLY valid JSON - no markdown, no explanation:
{"members": [...], "notes": "any special conditions observed"}"""

    try:
        # v3.5.6: migrated from deprecated google-generativeai to google-genai.
        # New SDK takes raw bytes via types.Part.from_bytes; the base64
        # encoding the legacy SDK accepted is no longer needed for the
        # in-process call. We keep pdf_b64 computed above for any caller
        # paths that still expect it on the function-scope locals.
        from bridge.gemini_compat import get_genai, get_types, make_client
        genai = get_genai(); types = get_types()
        client = make_client(api_key)
        pdf_part = types.Part.from_bytes(
            data=pdf_file.read_bytes(),
            mime_type="application/pdf",
        )

        # Send PDF to vision
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[prompt, pdf_part],
        )

        # Parse JSON response
        text = response.text.strip()
        # Clean markdown fences if present
        if text.startswith("```"):
            text = text.split("\n", 1)[1] if "\n" in text else text[3:]
        if text.endswith("```"):
            text = text[:-3]
        if text.startswith("json"):
            text = text[4:]

        result = json.loads(text.strip())
        members = result.get("members", [])

        return {
            "members": members,
            "member_count": len(members),
            "notes": result.get("notes", ""),
            "source": "gemini_vision",
            "pdf": pdf_path,
        }

    except json.JSONDecodeError as e:
        return {"error": f"AI returned invalid JSON: {e}", "raw_text": text[:500]}
    except Exception as e:
        err = str(e)
        if "429" in err or "quota" in err.lower():
            return {"error": "Gemini free tier limit reached (20/day). Upgrade billing or wait for reset."}
        return {"error": f"Vision extraction failed: {e}"}



# ── DECIMAL-TO-FRACTION NORMALIZATION ─────────────────────────────
# PDF extractors produce HSS8X8X.500 but fabrication DB uses HSS8X8X1/2
_DECIMAL_TO_FRACTION = {
    ".500": "1/2", ".5": "1/2", ".5000": "1/2",
    ".375": "3/8", ".3750": "3/8",
    ".250": "1/4", ".2500": "1/4", ".25": "1/4",
    ".625": "5/8", ".6250": "5/8",
    ".750": "3/4", ".7500": "3/4", ".75": "3/4",
    ".3125": "5/16", ".1875": "3/16",
    ".875": "7/8", ".8750": "7/8",
    ".125": "1/8", ".1250": "1/8",
    ".3130": "5/16", ".1880": "3/16",
}

def _normalize_shape_notation(shape: str) -> str:
    """Convert decimal thickness to fraction for AISC lookup.
    HSS8X8X.500 -> HSS8X8X1/2
    L4X4X.375 -> L4X4X3/8
    """
    # Find the last decimal component (thickness/wall)
    m = re.match(r'^(.*X)(\.\d+)$', shape)
    if m:
        prefix = m.group(1)
        decimal_part = m.group(2)
        fraction = _DECIMAL_TO_FRACTION.get(decimal_part)
        if fraction:
            return prefix + fraction
    return shape

def match_aisc_database(members: list) -> dict:
    """Step 3-4: Match each extracted member against local AISC database.

    Returns enriched members with exact dimensions, weights, and costs.
    100% LOCAL - no AI call.
    """
    from bridge.fabrication import get_section, _load_sections

    sections = _load_sections()
    matched = []
    unmatched = []
    total_weight = 0
    total_pieces = 0

    for m in members:
        shape = m.get("shape", "").upper().replace(" ", "").replace("×", "X")
        length_ft = float(m.get("length_ft", 0))
        qty = int(m.get("qty", 1))

        sec = get_section(shape)
        # If not found, try decimal-to-fraction (HSS8X8X.500 -> HSS8X8X1/2)
        if not sec:
            normalized = _normalize_shape_notation(shape)
            if normalized != shape:
                sec = get_section(normalized)
                if sec:
                    shape = normalized  # use the matched name going forward
        if sec:
            wt_per_ft = sec.get("W", sec.get("weight_per_foot", 0))
            member_weight = wt_per_ft * length_ft
            line_weight = member_weight * qty
            total_weight += line_weight
            total_pieces += qty

            matched.append({
                **m,
                "aisc_match": True,
                "depth_in": sec.get("d", 0),
                "flange_width_in": sec.get("bf", 0),
                "web_thickness_in": sec.get("tw", 0),
                "flange_thickness_in": sec.get("tf", 0),
                "weight_per_ft": wt_per_ft,
                "member_weight_lbs": round(member_weight, 1),
                "line_weight_lbs": round(line_weight, 1),
                "line_weight_tons": round(line_weight / 2000, 3),
            })
        else:
            unmatched.append({
                **m,
                "aisc_match": False,
                "note": f"Shape '{shape}' not in AISC database - manual review needed"
            })

    return {
        "matched": matched,
        "unmatched": unmatched,
        "summary": {
            "total_members": len(members),
            "matched_count": len(matched),
            "unmatched_count": len(unmatched),
            "total_pieces": total_pieces,
            "total_weight_lbs": round(total_weight, 1),
            "total_weight_tons": round(total_weight / 2000, 2),
        },
        "source": "AISC_LOCAL",
    }


def generate_cost_estimate(matched_data: dict, bid_rates: dict = None) -> dict:
    """Step 6: Generate cost estimate from matched members at current bid rates.

    LOCAL CALCULATION - uses bid rates from data/bid_rates.json.
    """
    if bid_rates is None:
        # Load from saved rates or use defaults
        rates_file = Path(__file__).resolve().parent.parent / "data" / "bid_rates.json"
        if rates_file.exists():
            bid_rates = json.loads(rates_file.read_text())
        else:
            bid_rates = {
                "fabrication_per_ton": 3750,
                "erection_per_ton": 970,
                "ga_percent": 7.5,
            }

    summary = matched_data["summary"]
    tons = summary["total_weight_tons"]

    fab_rate = bid_rates.get("fabrication_per_ton", 3750)
    erect_rate = bid_rates.get("erection_per_ton", 970)
    ga_pct = bid_rates.get("ga_percent", 7.5)

    fab_cost = tons * fab_rate
    erect_cost = tons * erect_rate
    subtotal = fab_cost + erect_cost
    ga_cost = subtotal * (ga_pct / 100)
    total = subtotal + ga_cost

    return {
        "tonnage": tons,
        "fabrication": {"rate": fab_rate, "cost": round(fab_cost, 2)},
        "erection": {"rate": erect_rate, "cost": round(erect_cost, 2)},
        "subtotal": round(subtotal, 2),
        "ga": {"percent": ga_pct, "cost": round(ga_cost, 2)},
        "total_estimate": round(total, 2),
        "per_ton": round(total / tons, 2) if tons > 0 else 0,
        "source": "LOCAL_CALCULATION",
    }


def run_hybrid_3d_pipeline(pdf_path: str, api_key: str = "",
                            bid_rates: dict = None) -> dict:
    """Full hybrid pipeline: PDF → Vision → AISC Match → Cost Estimate.

    This is a BID PIPELINE STEP - generates an accurate takeoff from drawings.
    """
    result = {"pipeline": "hybrid_3d", "started": datetime.now(timezone.utc).isoformat()}

    # Step 1-2: AI Vision extracts members
    extraction = extract_members_from_pdf(pdf_path, api_key)
    if "error" in extraction:
        return {**result, "error": extraction["error"], "step_failed": "vision_extraction"}

    result["extraction"] = {
        "member_count": extraction["member_count"],
        "notes": extraction.get("notes", ""),
    }

    # Step 3-4: LOCAL AISC matching
    matched = match_aisc_database(extraction["members"])
    result["aisc_match"] = matched["summary"]
    result["members"] = matched["matched"]
    result["unmatched"] = matched["unmatched"]

    # Step 5: Generate STL (if members found)
    if matched["matched"]:
        try:
            from bridge.fabrication import generate_stl as fab_stl
            stl_members = []
            x_offset = 0
            for m in matched["matched"]:
                for i in range(int(m.get("qty", 1))):
                    stl_members.append({
                        "shape": m["shape"],
                        "length_ft": m.get("length_ft", 20),
                        "x_ft": x_offset,
                        "y_ft": 0,
                        "z_ft": 0,
                        "mark": f"{m.get('mark', '?')}-{i+1}",
                    })
                    x_offset += (m.get("flange_width_in", 12) / 12) + 3
            stl_bytes = fab_stl(stl_members)
            # Save STL
            out_dir = Path(__file__).resolve().parent.parent / "output"
            out_dir.mkdir(parents=True, exist_ok=True)
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")  # vj: local-display-ok
            stl_filename = f"takeoff_3d_{ts}.stl"
            stl_path = out_dir / stl_filename
            stl_path.write_bytes(stl_bytes)
            result["stl"] = {
                "path": str(stl_path),
                "filename": stl_filename,
                "size_bytes": len(stl_bytes),
                "member_count": len(stl_members),
            }
        except Exception as e:
            result["stl_error"] = str(e)

    # Step 6: Cost estimate
    estimate = generate_cost_estimate(matched, bid_rates)
    result["estimate"] = estimate

    # Summary message
    s = matched["summary"]
    e = estimate
    unmatched_note = ""
    if s['unmatched_count'] > 0:
        unmatched_note = f" ({s['unmatched_count']} need manual review)"
    result["message"] = (
        f"✅ Hybrid 3D Pipeline Complete\n\n"
        f"📄 PDF: {Path(pdf_path).name}\n"
        f"🔍 Vision extracted: {s['total_members']} member types, {s['total_pieces']} total pieces\n"
        f"✓ AISC matched: {s['matched_count']}/{s['total_members']}{unmatched_note}\n"
        f"⚖ Total weight: {s['total_weight_lbs']:,.0f} lbs ({s['total_weight_tons']:.2f} tons)\n\n"
        f"💰 Estimate at current bid rates:\n"
        f"   Fabrication: ${e['fabrication']['cost']:,.0f} (${e['fabrication']['rate']:,.0f}/ton)\n"
        f"   Erection: ${e['erection']['cost']:,.0f} (${e['erection']['rate']:,.0f}/ton)\n"
        f"   G&A ({e['ga']['percent']}%): ${e['ga']['cost']:,.0f}\n"
        f"   ─────────────────\n"
        f"   TOTAL: ${e['total_estimate']:,.0f}\n"
    )

    result["completed"] = datetime.now(timezone.utc).isoformat()
    return result
