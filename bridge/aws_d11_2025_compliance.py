"""
Your Company Virtual Office - AWS D1.1:2025 Essential Variable Tracker

4 new hooks per handoff document §5:
  1. Pulsed-spray GMAW - dedicated prequalified WPS shielding-gas tables (Table 5.7)
  2. Type-D studs - ASTM A706 Gr. 60 requires fillet-weld qualification per D1.4
  3. Plug/slot welds - own WPS qualification + macroetch requirements
  4. Preheat extension - thickness-based (≥2t under 1.5", ≥t and ≥3" above)
     PWHT max raised 600°F → 800°F
"""

from datetime import datetime, timezone

# AWS D1.1:2025 essential variable changes
D11_2025_CHANGES = {
    "pulsed_spray_gmaw": {
        "clause": "Table 5.7",
        "description": "Pulsed-spray GMAW now has dedicated prequalified WPS shielding-gas tables",
        "conforming_specs": ["AWS A5.18", "AWS A5.18M"],
        "shielding_gases": {
            "75Ar_25CO2": {"status": "prequalified", "transfer": "pulsed_spray"},
            "90Ar_10CO2": {"status": "prequalified", "transfer": "pulsed_spray"},
            "100CO2": {"status": "NOT prequalified for pulsed_spray", "transfer": "short_circuit_only"},
        },
        "essential_variables": [
            "Shielding gas composition",
            "Transfer mode (pulsed vs. conventional spray)",
            "Wire electrode specification",
            "Wire diameter",
        ],
    },
    "type_d_studs": {
        "clause": "D1.4 cross-reference",
        "description": "Type-D studs (deformed bar/wire ASTM A706 Gr. 60) require fillet-weld qualification per AWS D1.4",
        "material_spec": "ASTM A706 Grade 60",
        "qualification_requirement": "Fillet weld per AWS D1.4",
        "essential_variables": [
            "Stud diameter",
            "Base metal thickness",
            "Stud material specification (A706 vs A108)",
            "Weld process (arc stud welding vs. fillet)",
        ],
    },
    "plug_slot_welds": {
        "clause": "Clause 5 (new subsection)",
        "description": "Plug/slot welds now have their own WPS qualification and macroetch requirements",
        "qualification": {
            "test_required": "macroetch",
            "specimens": "3 cross-sections minimum",
            "acceptance": "Complete fusion, no cracks",
        },
        "essential_variables": [
            "Hole diameter (plug) or slot dimensions",
            "Base metal thickness",
            "Filler depth",
            "Weld process",
        ],
    },
    "preheat_pwht": {
        "clause": "Clause 5 Table 5.8 (revised)",
        "description": "Preheat extension distance now thickness-based; PWHT max furnace temp raised from 600°F to 800°F",
        "preheat_extension": {
            "under_1_5_inch": "≥ 2t (where t = thickness of thicker part)",
            "over_1_5_inch": "≥ t AND ≥ 3 inches",
        },
        "pwht": {
            "max_furnace_temp_old": 600,
            "max_furnace_temp_2025": 800,
            "unit": "°F",
            "note": "When furnace temperature exceeds 800°F during loading, member shall be removed",
        },
        "essential_variables": [
            "Base metal thickness",
            "Preheat temperature",
            "Preheat extension distance",
            "PWHT temperature and hold time",
            "PWHT max loading temperature",
        ],
    },
}


def check_wps_compliance(wps: dict, code_year: str = "2025") -> dict:
    """Check a WPS against 2025 essential variable requirements.

    wps: {process, transfer_mode, shielding_gas, base_metal_thickness,
          stud_type, weld_type, preheat_temp, pwht_temp, ...}
    """
    findings = []
    process = wps.get("process", "").upper()
    transfer = wps.get("transfer_mode", "").lower()

    if code_year == "2020":
        return {"findings": [], "note": "Project references D1.1:2020 - 2025 checks skipped",
                "code_year": "2020", "compliant": True}

    # Check 1: Pulsed-spray GMAW shielding gas
    if process in ("GMAW", "GMAW-P") and "pulsed" in transfer:
        gas = wps.get("shielding_gas", "")
        gas_data = D11_2025_CHANGES["pulsed_spray_gmaw"]["shielding_gases"]
        gas_key = gas.replace(" ", "").replace("/", "_")
        matched = False
        for key, val in gas_data.items():
            if key.lower().replace("_", "") in gas.lower().replace(" ", "").replace("/", ""):
                if "NOT" in val["status"]:
                    findings.append({"severity": "FAIL",
                        "msg": f"Shielding gas '{gas}' is NOT prequalified for pulsed-spray per Table 5.7"})
                else:
                    findings.append({"severity": "PASS",
                        "msg": f"Shielding gas '{gas}' is prequalified for pulsed-spray"})
                matched = True
                break
        if not matched and gas:
            findings.append({"severity": "WARN",
                "msg": f"Shielding gas '{gas}' not found in Table 5.7 - verify manually"})

    # Check 2: Type-D studs
    if wps.get("stud_type", "").upper() in ("TYPE-D", "D", "A706"):
        findings.append({"severity": "WARN",
            "msg": "Type-D studs (A706 Gr. 60) require fillet-weld qualification per AWS D1.4"})

    # Check 3: Plug/slot welds
    if wps.get("weld_type", "").lower() in ("plug", "slot", "plug_weld", "slot_weld"):
        findings.append({"severity": "INFO",
            "msg": "Plug/slot welds require dedicated WPS qualification with macroetch per D1.1:2025"})

    # Check 4: Preheat extension and PWHT
    thickness = wps.get("base_metal_thickness", 0)
    if thickness > 0:
        if thickness <= 1.5:
            min_ext = 2 * thickness
            findings.append({"severity": "INFO",
                "msg": f"Preheat extension: ≥ {min_ext:.2f}\" (2t for t ≤ 1.5\")"})
        else:
            min_ext = max(thickness, 3.0)
            findings.append({"severity": "INFO",
                "msg": f"Preheat extension: ≥ {min_ext:.1f}\" (≥t and ≥3\" for t > 1.5\")"})

    pwht_temp = wps.get("pwht_temp", 0)
    if pwht_temp > 800:
        findings.append({"severity": "FAIL",
            "msg": f"PWHT temp {pwht_temp}°F exceeds 2025 max furnace loading temp of 800°F"})
    elif pwht_temp > 600:
        findings.append({"severity": "INFO",
            "msg": f"PWHT temp {pwht_temp}°F - compliant with 2025 (max 800°F), would have FAILED under 2020 (max 600°F)"})

    return {
        "code_year": code_year,
        "findings": findings,
        "compliant": not any(f["severity"] == "FAIL" for f in findings),
        "warnings": sum(1 for f in findings if f["severity"] == "WARN"),
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }


def get_2025_changes() -> dict:
    """Return all D1.1:2025 essential variable changes for reference."""
    return D11_2025_CHANGES


def get_essential_variables_for_process(process: str) -> list:
    """Get required essential variables for a welding process under 2025."""
    evs = set()
    for change in D11_2025_CHANGES.values():
        for ev in change.get("essential_variables", []):
            evs.add(ev)
    return sorted(evs)
