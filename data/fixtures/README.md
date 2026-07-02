# Fixtures

Synthetic test inputs for the structural drawing pipeline. These are NOT
real bid drawings - they exercise specific code paths without exposing
client data.

## sample_drawing.pdf

A minimal synthetic structural set with three schedules: columns, beams,
joists. Added in pass 10f (roadmap item #7) so the takeoff pipeline can
be exercised without uploading a real client PDF.

Exercise it via:

```python
b = Bridge()
result = b.auto_process_drawing("data/fixtures/sample_drawing.pdf")
# Expect: ok=True, total_tonnage approximately 30.7
```

### What this fixture COVERS

- `auto_process_drawing` end-to-end ok=True path
- Page extraction (single page, text-based)
- Aggregate tonnage extraction from schedule tables (column / beam /
  joist totals)
- Graceful handling of a thin synthetic input by the downstream chain

### What this fixture does NOT cover

The fixture intentionally tests the AGGREGATE extraction path only. It
does not exercise:

- Member-by-member enumeration. The canonical extractor expects member
  rows in a specific table format (per-mark rows with shape/size/length
  columns). The fixture uses schedule-summary text only, so
  `members[]` returns empty and `member_count=None`.
- STL generation. `stl_path` returns None because no individual member
  geometry is available.
- AESS Cat 3/4 detection. No AESS notes in the synthetic text.
- Misc-steel detection (lintels, stairs, rails). Not present in the
  fixture.
- Connection design verification. No connection details in the
  fixture.

To exercise the full member-enumeration pipeline, use a real bid PDF
with the standard MEMBER LIST table format (mark / shape / length /
quantity columns) under `data/bids/<bid_number>/` per the Owner's normal
intake flow. Real-PDF fixtures stay out of the shipped zip per the
standing rule against shipping client data.

### Pass 10g audit verdict

Reviewed during pass 10g live walk-through (Item B.3). Confirmed the
fixture is functioning as designed for the aggregate path. Adding a
member-row test fixture is deferred until there is a need to exercise
the canonical extractor in CI; today's manual smoke test covers it via
real bid PDFs in the Owner's working directory.
