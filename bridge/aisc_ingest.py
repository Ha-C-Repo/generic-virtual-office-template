"""
AISC v16.0 Full Database Ingestion Script
==========================================
Converts the raw aisc-shapes-v160-US.csv (2,299 rows, 84 columns)
into the production aisc_master.csv used by AISCValidator.

Source: AISC Steel Construction Manual 16th Edition
File: aisc-shapes-v160-US.csv (in Claude Project knowledge)
Columns needed: Type, AISC_Manual_Label, W, A, d, bf, tf, tw, rx, ry, T, kdes

Usage:
    python bridge/aisc_ingest.py data/aisc-shapes-v160-US.csv

Output:
    data/aisc_master.csv (2,299 rows, 12 essential columns)
    
After running, update aisc_validator.py to point to aisc_master.csv.
"""

import sys
import pandas as pd
from pathlib import Path


# Columns we need for the Math Firewall
ESSENTIAL_COLS = [
    'Type',                 # W, HSS, C, L, HP, MC, S, WT, PIPE, 2L, MT, ST
    'AISC_Manual_Label',    # Human-readable: W14X82, HSS6X6X1/2, etc.
    'W',                    # Weight per foot (lb/ft)
    'A',                    # Cross-sectional area (in^2)
    'd',                    # Depth (in)
    'bf',                   # Flange width (in)
    'tf',                   # Flange thickness (in)
    'tw',                   # Web thickness (in)
    'rx',                   # Radius of gyration, x-axis (in)
    'ry',                   # Radius of gyration, y-axis (in)
    'T',                    # T-distance: clear distance between flanges minus k (in)
                            # Used for k-zone bolt clearance check
    'kdes',                 # Design k-distance: fillet-to-flange (in)
]


def ingest(csv_path: str, output_path: str = "data/aisc_master.csv") -> dict:
    """Ingest full AISC v16.0 CSV into production format.
    
    Returns:
        dict with shape_count, families, file_size_kb
    """
    df = pd.read_csv(csv_path)
    
    # Keep only essential columns (some may be missing for certain shapes)
    available = [c for c in ESSENTIAL_COLS if c in df.columns]
    master = df[available].copy()
    
    # Clean up: replace dashes with NaN
    master = master.replace('-', pd.NA)
    master = master.replace('-', pd.NA)
    
    # Convert numeric columns
    for col in ['W', 'A', 'd', 'bf', 'tf', 'tw', 'rx', 'ry', 'T', 'kdes']:
        if col in master.columns:
            master[col] = pd.to_numeric(master[col], errors='coerce')
    
    # Rename for consistency with existing validator and connection_check
    master = master.rename(columns={
        'AISC_Manual_Label': 'shape',
        'W': 'lb_per_ft',
        'Type': 'family',
        # Legacy validator/connection_check hard-coded suffixes
        'A': 'A_in2',
        'd': 'd_in',
        'bf': 'bf_in',
        'tf': 'tf_in',
        'tw': 'tw_in',
        'rx': 'rx_in',
        'ry': 'ry_in',
        # T and kdes are new (no legacy equivalent) - keep as-is
    })
    
    # Drop rows with no shape name
    master = master.dropna(subset=['shape'])
    
    # Save
    out = Path(output_path)
    master.to_csv(out, index=False)
    
    families = master['family'].value_counts().to_dict()
    
    return {
        "shape_count": len(master),
        "families": families,
        "columns": list(master.columns),
        "file_size_kb": round(out.stat().st_size / 1024, 1),
    }


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python bridge/aisc_ingest.py <path-to-aisc-shapes-v160-US.csv>")
        print("  The CSV is in the Claude Project knowledge at claude.ai")
        print("  Download it and pass the path to this script.")
        sys.exit(1)
    
    result = ingest(sys.argv[1])
    print(f"Ingested {result['shape_count']} shapes")
    print(f"Families: {result['families']}")
    print(f"Output: data/aisc_master.csv ({result['file_size_kb']} KB)")
