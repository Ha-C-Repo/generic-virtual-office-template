"""
Davis-Bacon Wages - Data Fabric Layer

Per-classification rate lookup with fringe for Houston (Harris County).
Separates Building vs Engineering Construction (most common bidding error).
Quarterly refresh from SAM.gov wage-determination XML + City of Houston OBO PDFs.

CRITICAL: Private commercial work is generally NOT prevailing-wage.
System defaults to Davis-Bacon=OFF; requires explicit toggle per project.
"""
from pathlib import Path

_DATA = Path(__file__).resolve().parent.parent / "data"
_WAGES_FILE = _DATA / "davis_bacon_wages.json"

# Houston Building Construction 2025-2026 rates (from handoff doc + SAM.gov WD)
BUILDING_CONSTRUCTION_HOUSTON = {
    "Structural Ironworker (Erector)": {"base": 42.50, "fringe": 22.89, "total": 65.39,
        "note": "Local 84 range $40-$45/hr + per diem on travel"},
    "Structural Ironworker (Reinforcing)": {"base": 29.47, "fringe": 16.36, "total": 45.83},
    "Welder / Combo Welder (6G)": {"base": 42.50, "fringe": 22.89, "total": 65.39,
        "note": "Non-prevailing shop: $23-$36 national, Houston +9%"},
    "Crane Operator (NCCCO)": {"base": 38.25, "fringe": 18.50, "total": 56.75,
        "note": "Required for structural picks over standard"},
    "Painter (Structural Steel)": {"base": 25.50, "fringe": 14.20, "total": 39.70},
    "Truck Driver (Heavy)": {"base": 22.75, "fringe": 12.50, "total": 35.25},
    "Laborer (General)": {"base": 16.25, "fringe": 10.80, "total": 27.05},
    "Electrician": {"base": 38.75, "fringe": 21.30, "total": 60.05},
    "Plumber / Pipefitter": {"base": 40.50, "fringe": 22.10, "total": 62.60},
    "Sheet Metal Worker": {"base": 33.50, "fringe": 19.80, "total": 53.30},
}

# Engineering Construction (highway/civil) - DISTINCT from Building
# "Confusing them is the most common bidding error for small shops" - handoff doc
ENGINEERING_CONSTRUCTION_HOUSTON = {
    "Common Laborer": {"base": 11.02, "fringe": 5.50, "total": 16.52,
        "note": "City of Houston Engineering schedule - NOT building rates"},
    "Form Setter (Structures)": {"base": 12.23, "fringe": 6.10, "total": 18.33},
    "Ironworker": {"base": 30.50, "fringe": 16.00, "total": 46.50},
    "Crane Operator": {"base": 34.00, "fringe": 16.50, "total": 50.50},
    "Welder": {"base": 30.50, "fringe": 16.00, "total": 46.50},
}

# EO minimums (updated annually)
EO_MINIMUMS = {
    "EO-14026": {"min_wage": 17.75, "effective": "2026-01-01",
                  "note": "Federal contracts entered/renewed after 1/30/2022"},
    "EO-13658": {"min_wage": 13.50, "effective": "2026-01-01",
                  "note": "Federal contracts entered before 1/30/2022"},
}


def get_rates(contract_type="building"):
    """Get Davis-Bacon rates for Houston.
    contract_type: 'building' or 'engineering'
    """
    if contract_type.lower().startswith("eng"):
        rates = ENGINEERING_CONSTRUCTION_HOUSTON
        label = "Engineering Construction (Highway/Civil)"
    else:
        rates = BUILDING_CONSTRUCTION_HOUSTON
        label = "Building Construction"
    return {
        "contract_type": label,
        "location": "Houston, Harris County TX",
        "source": "SAM.gov General Decision + City of Houston OBO 2025",
        "rates": rates,
        "eo_minimums": EO_MINIMUMS,
        "last_updated": "2025-Q4",
        "warning": "Private commercial work is generally NOT prevailing-wage. Check bid docs.",
    }


def lookup_classification(title, contract_type="building"):
    """Look up a specific classification by partial name match."""
    rates = get_rates(contract_type)["rates"]
    matches = []
    for cls_name, data in rates.items():
        if title.lower() in cls_name.lower():
            matches.append({"classification": cls_name, **data})
    return matches if matches else [{"error": f"No match for '{title}' in {contract_type} rates"}]


def validate_rate(classification, billed_rate, contract_type="building"):
    """Validate a billed rate against Davis-Bacon minimums.
    Returns {compliant, minimum, billed, shortfall}."""
    matches = lookup_classification(classification, contract_type)
    if matches and not matches[0].get("error"):
        minimum = matches[0]["total"]
        return {
            "classification": matches[0]["classification"],
            "minimum_total": minimum,
            "billed_rate": billed_rate,
            "compliant": billed_rate >= minimum,
            "shortfall": round(max(0, minimum - billed_rate), 2),
        }
    return {"error": f"Classification '{classification}' not found"}


def project_rate_table(contract_type="building", crew_mix=None):
    """Generate a rate table for a project bid.
    crew_mix: dict of {classification: headcount} or None for all."""
    rates = get_rates(contract_type)["rates"]
    table = []
    for cls_name, data in rates.items():
        if crew_mix and not any(k.lower() in cls_name.lower() for k in crew_mix):
            continue
        table.append({
            "classification": cls_name,
            "base": data["base"],
            "fringe": data["fringe"],
            "total": data["total"],
        })
    return {
        "contract_type": contract_type,
        "table": table,
        "eo_14026_minimum": EO_MINIMUMS["EO-14026"]["min_wage"],
    }


def is_davis_bacon_project(owner):
    """Check if a project owner typically requires Davis-Bacon.
    Per handoff: City of Houston, METRO, Harris County, HHD, TFC, CCMI listed neighbors."""
    db_owners = [
        "city of houston", "houston airports", "metro", "harris county",
        "harris county hospital", "texas facilities commission", "ccmi",
        "pasadena", "baytown", "texas city", "galveston county",
    ]
    return any(o in owner.lower() for o in db_owners)
