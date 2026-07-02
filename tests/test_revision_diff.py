"""Tests for the T10 revision diff (Prompt 7). Synthetic two-issue
PDFs exercise both passes end to end: a changed designation at the
same location, an added and a removed callout, a pure geometry change
(a drawn line) only the pixel pass can see, the alignment sign
convention, the scanned pixel-only path, sheet auto-pairing, and the
_DIFF overlay plus takeoff_delta.md outputs."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

from takeoff_pipeline import revision_diff
from takeoff_pipeline.revision_diff import (
    _merge_regions,
    _pair_changed,
    _vector_diff,
    pair_sheets,
    run_revision_diff,
)

LINE_Y = 500.0


def _build_issues(old_path, new_path):
    """Old issue: W12X26, 28K7, C8X11.5. New issue: W12X26 becomes
    W14X30 at the same spot, 28K7 removed, HSS6X6X1/4 added, plus a
    drawn line (geometry only, no text)."""
    import fitz

    doc = fitz.open()
    page = doc.new_page(width=612, height=792)
    _filler(page)
    page.insert_text((100, 100), "W12X26")
    page.insert_text((300, 200), "28K7")
    page.insert_text((150, 300), "C8X11.5")
    doc.save(str(old_path))
    doc.close()

    doc = fitz.open()
    page = doc.new_page(width=612, height=792)
    _filler(page)
    page.insert_text((100, 100), "W14X30")
    page.insert_text((150, 300), "C8X11.5")
    page.insert_text((300, 400), "HSS6X6X1/4")
    page.draw_line((400, LINE_Y), (500, LINE_Y), width=3)
    doc.save(str(new_path))
    doc.close()


def _filler(page, dx=0.0, dy=0.0, sid="S-101"):
    """Unchanged content on both issues: a sheet id in the
    bottom-right strip for pairing, plus enough words and linework
    that the scanned threshold and phase correlation have signal."""
    page.insert_text((520 + dx, 700 + dy), sid)
    for i in range(40):
        page.insert_text((60 + dx + (i % 5) * 100,
                          560 + dy + (i // 5) * 14),
                         f"NOTE{i} TYP UNO")
    import fitz

    page.draw_rect(fitz.Rect(40 + dx, 40 + dy, 580 + dx, 540 + dy))


@pytest.fixture()
def sandbox_handoff(tmp_path, monkeypatch):
    monkeypatch.setattr(revision_diff, "HANDOFF_ROOT",
                        tmp_path / "_handoff")


def test_full_diff_end_to_end(tmp_path, sandbox_handoff):
    old_pdf = tmp_path / "old.pdf"
    new_pdf = tmp_path / "new.pdf"
    _build_issues(old_pdf, new_pdf)

    info = run_revision_diff(old_pdf, new_pdf, out_dir=tmp_path)

    assert info["pairs_diffed"] == 1
    sheet = info["sheets"][0]
    assert sheet["sheet"] == "S-101"
    assert sheet["mode"] == revision_diff.MODE_FULL

    out_pdf = Path(info["out_pdf"])
    report = Path(info["report"])
    assert out_pdf.name == "new_DIFF.pdf" and out_pdf.exists()
    assert report.name == "takeoff_delta.md" and report.exists()

    text = report.read_text(encoding="utf-8")
    # Governance: no em-dashes anywhere in generated output.
    assert "—" not in text and "–" not in text
    # Callout delta: changed pair counts as -1/+1, removal, addition;
    # the unchanged C8X11.5 must not appear as a delta row.
    for needle in ("W12X26", "W14X30", "28K7", "HSS6X6X1/4"):
        assert needle in text
    assert "| `C8X11.5` |" not in text
    assert "INTERNAL" in text

    deltas = {}
    for res_sheet in _report_rows(text):
        deltas[res_sheet[0]] = res_sheet[1]
    assert deltas["W12X26"] == -1
    assert deltas["W14X30"] == +1
    assert deltas["28K7"] == -1
    assert deltas["HSS6X6X1/4"] == +1


def _report_rows(text):
    """(designation, delta) rows parsed back out of the md table."""
    out = []
    for line in text.splitlines():
        if line.startswith("| `") and line.count("|") >= 6:
            cells = [c.strip() for c in line.strip("|").split("|")]
            out.append((cells[0].strip("`"), int(cells[4])))
    return out


def test_changed_pair_and_geometry_region(tmp_path, sandbox_handoff):
    import fitz

    old_pdf = tmp_path / "old.pdf"
    new_pdf = tmp_path / "new.pdf"
    _build_issues(old_pdf, new_pdf)

    old_doc = fitz.open(str(old_pdf))
    new_doc = fitz.open(str(new_pdf))
    try:
        res = revision_diff.diff_pair(old_doc, 0, new_doc, 0, "S-101")
    finally:
        old_doc.close()
        new_doc.close()

    changed = {(c["old_text"], c["new_text"])
               for c in res["vector"]["changed"]}
    assert ("W12X26", "W14X30") in changed

    # The drawn line has no text; only the pixel pass can see it.
    def covers_line(r):
        return (r[0] <= 450 <= r[2]
                and r[1] - 4 <= LINE_Y <= r[3] + 4)

    assert any(covers_line(r) for r in res["pixel"]["regions"])


def test_overlay_carries_red_annotations(tmp_path, sandbox_handoff):
    import fitz

    old_pdf = tmp_path / "old.pdf"
    new_pdf = tmp_path / "new.pdf"
    _build_issues(old_pdf, new_pdf)
    info = run_revision_diff(old_pdf, new_pdf, out_dir=tmp_path)

    doc = fitz.open(info["out_pdf"])
    try:
        annots = list(doc[0].annots())
        assert annots
        titles = {a.info.get("title", "") for a in annots}
        assert "changed region (pixel pass)" in titles
        assert "changed text" in titles
        assert "added callout" in titles
        assert "removed callout" in titles
        for a in annots:
            content = a.info.get("content", "")
            assert "—" not in content and "–" not in content
    finally:
        doc.close()


def test_alignment_absorbs_uniform_shift(tmp_path, sandbox_handoff):
    """The new issue is the same drawing shifted 5 pt right and 3 pt
    down. Alignment must absorb the shift (few or no changed regions)
    and report it with the correct sign."""
    import fitz

    old_pdf = tmp_path / "old.pdf"
    new_pdf = tmp_path / "new.pdf"
    for path, dx, dy in ((old_pdf, 0.0, 0.0), (new_pdf, 5.0, 3.0)):
        doc = fitz.open()
        page = doc.new_page(width=612, height=792)
        _filler(page, dx, dy)
        doc.save(str(path))
        doc.close()

    old_doc = fitz.open(str(old_pdf))
    new_doc = fitz.open(str(new_pdf))
    try:
        res = revision_diff.diff_pair(old_doc, 0, new_doc, 0, "S-101")
    finally:
        old_doc.close()
        new_doc.close()

    shift = res["pixel"]["shift_pt"]
    assert abs(shift[0] - 5.0) <= 1.0 and abs(shift[1] - 3.0) <= 1.0
    assert not res["pixel"]["shift_rejected"]
    assert len(res["pixel"]["regions"]) <= 2
    vec_shift = res["vector"]["median_shift_pt"]
    assert abs(vec_shift[0] - 5.0) <= 0.5
    assert abs(vec_shift[1] - 3.0) <= 0.5


def test_scanned_input_runs_pixel_only(tmp_path, sandbox_handoff):
    import fitz

    old_pdf = tmp_path / "old.pdf"
    new_pdf = tmp_path / "new.pdf"
    _build_issues(old_pdf, new_pdf)

    # Rasterize the old issue: image-only page, zero text words.
    scanned_pdf = tmp_path / "old_scanned.pdf"
    src = fitz.open(str(old_pdf))
    scan = fitz.open()
    page = scan.new_page(width=612, height=792)
    page.insert_image(page.rect,
                      pixmap=src[0].get_pixmap(matrix=fitz.Matrix(2,
                                                                  2)))
    scan.save(str(scanned_pdf))
    scan.close()
    src.close()

    info = run_revision_diff(scanned_pdf, new_pdf,
                             pairs=[(0, 0, "S-101")],
                             out_dir=tmp_path)
    sheet = info["sheets"][0]
    assert sheet["mode"] == revision_diff.MODE_PIXEL_ONLY
    assert sheet["callout_delta_rows"] is None
    text = Path(info["report"]).read_text(encoding="utf-8")
    assert "PIXEL ONLY" in text
    assert "scanned or non-vector" in text


def test_pair_sheets_matches_by_id_not_position(tmp_path):
    import fitz

    def build(path, ids):
        doc = fitz.open()
        for sid in ids:
            page = doc.new_page(width=612, height=792)
            _filler(page, sid=sid)
        doc.save(str(path))
        doc.close()

    old_pdf = tmp_path / "a.pdf"
    new_pdf = tmp_path / "b.pdf"
    build(old_pdf, ["S-201", "S-202"])
    build(new_pdf, ["S-202", "S-201"])  # reversed order

    pairing = pair_sheets(old_pdf, new_pdf)
    pairs = {p["sheet"]: (p["old_page"], p["new_page"])
             for p in pairing["pairs"]}
    assert pairs["S-201"] == (0, 1)
    assert pairs["S-202"] == (1, 0)


def test_vector_diff_units():
    old = [("W12X26", (100, 100, 130, 108)),
           ("TYP", (200, 200, 215, 208)),
           ("28K7", (300, 300, 322, 308))]
    new = [("W14X30", (100, 100, 130, 108)),
           ("TYP", (200, 200, 215, 208)),
           ("HSS8X8X1/4", (400, 600, 460, 608))]
    res = _vector_diff(old, new)
    assert [c["old_text"] for c in res["changed"]] == ["W12X26"]
    assert [c["new_text"] for c in res["changed"]] == ["W14X30"]
    assert [a["text"] for a in res["added"]] == ["HSS8X8X1/4"]
    assert [r["text"] for r in res["removed"]] == ["28K7"]


def test_pair_changed_respects_distance_cap():
    near_old = [("W12X26", (100, 100, 130, 108))]
    near_new = [("W14X30", (102, 101, 132, 109))]
    changed, removed, added = _pair_changed(near_old, near_new,
                                            (0.0, 0.0))
    assert len(changed) == 1 and not removed and not added

    far_new = [("W14X30", (400, 500, 430, 508))]
    changed, removed, added = _pair_changed(near_old, far_new,
                                            (0.0, 0.0))
    assert not changed and len(removed) == 1 and len(added) == 1


def test_merge_regions():
    merged = _merge_regions([(0, 0, 10, 10), (12, 0, 20, 10),
                             (100, 100, 110, 110)], pad=4.0)
    assert len(merged) == 2
    assert (0, 0, 20, 10) in merged
    assert (100, 100, 110, 110) in merged


def test_median_immune_to_repeated_token_insertion():
    """One inserted instance of a 450-strong identical token family
    (dimension ticks) must not fake a page shift, invent relocations,
    or break same-location changed pairing."""
    tick = "30'-0\""
    old = [(tick, (i * 60.0, 500.0, i * 60.0 + 24, 508.0))
           for i in range(450)]
    new = [(tick, (-60.0, 500.0, -36.0, 508.0))]
    new += [(tick, (i * 60.0, 500.0, i * 60.0 + 24, 508.0))
            for i in range(450)]
    for words in (old, new):
        for k in range(30):
            words.append((f"UNIQ{k}", (40.0 + k * 9, 60.0,
                                       70.0 + k * 9, 68.0)))
        words.append(("W12X26", (100.0, 100.0, 130.0, 108.0)))
    old.append(("28K7", (700.0, 900.0, 722.0, 908.0)))
    new.append(("28K9", (700.0, 900.0, 722.0, 908.0)))

    res = _vector_diff(old, new)
    assert res["median_shift_pt"] == (0.0, 0.0)
    assert res["moved_count"] == 0
    assert res["moved_designations"] == []
    assert {(c["old_text"], c["new_text"])
            for c in res["changed"]} == {("28K7", "28K9")}
    assert [a["text"] for a in res["added"]] == [tick]
    assert res["removed"] == []


def test_greedy_family_pairing_does_not_cascade():
    """Distance-first pairing inside a small identical-token family:
    an instance inserted ahead of the others must become the single
    added word, not shift every pairing one slot over."""
    tick = "TYP"
    old = [(tick, (i * 60.0, 500.0, i * 60.0 + 14, 508.0))
           for i in range(10)]
    new = [(tick, (-60.0, 500.0, -46.0, 508.0))] + list(old)
    res = _vector_diff(old, new)
    assert res["moved_count"] == 0
    assert len(res["added"]) == 1
    assert res["added"][0]["bbox"][0] == -60.0
    assert res["removed"] == [] and res["changed"] == []


def test_rotated_pages_pixel_and_text_spaces_agree(tmp_path,
                                                   sandbox_handoff):
    """On /Rotate 90 pages, the pixel-pass regions, the vector text
    bboxes, and the drawn annotations must all land in the same
    coordinate space."""
    import fitz

    old_pdf = tmp_path / "old.pdf"
    new_pdf = tmp_path / "new.pdf"
    for path, tag in ((old_pdf, "W12X26"), (new_pdf, "W14X30")):
        doc = fitz.open()
        page = doc.new_page(width=612, height=792)
        _filler(page)
        page.insert_text((200, 400), tag)
        page.set_rotation(90)
        doc.save(str(path))
        doc.close()

    info = run_revision_diff(old_pdf, new_pdf,
                             pairs=[(0, 0, "ROT")], out_dir=tmp_path)
    doc = fitz.open(info["out_pdf"])
    try:
        page = doc[0]
        words = {w[4]: (w[0], w[1], w[2], w[3])
                 for w in page.get_text("words")}
        bb = words["W14X30"]
        cx, cy = (bb[0] + bb[2]) / 2, (bb[1] + bb[3]) / 2
        rects = [a.rect for a in page.annots()
                 if a.info.get("title") == "changed region "
                                           "(pixel pass)"]
        assert any(r.x0 - 2 <= cx <= r.x1 + 2
                   and r.y0 - 2 <= cy <= r.y1 + 2 for r in rects)
        changed = [a.rect for a in page.annots()
                   if a.info.get("title") == "changed text"]
        assert any(r.contains(fitz.Point(cx, cy)) for r in changed)
    finally:
        doc.close()


def test_old_diff_input_refused(tmp_path, sandbox_handoff):
    import shutil

    old_pdf = tmp_path / "old.pdf"
    new_pdf = tmp_path / "new.pdf"
    _build_issues(old_pdf, new_pdf)
    relabeled = tmp_path / "old_DIFF.pdf"
    shutil.copy2(old_pdf, relabeled)
    with pytest.raises(ValueError, match="old issue input"):
        run_revision_diff(relabeled, new_pdf, out_dir=tmp_path)


def test_duplicate_new_page_refused(tmp_path, sandbox_handoff):
    old_pdf = tmp_path / "old.pdf"
    new_pdf = tmp_path / "new.pdf"
    _build_issues(old_pdf, new_pdf)
    with pytest.raises(ValueError, match="more than one pair"):
        run_revision_diff(old_pdf, new_pdf,
                          pairs=[(0, 0), (0, 0)], out_dir=tmp_path)


def test_backup_collision_in_same_second_uniquified(tmp_path,
                                                    monkeypatch):
    monkeypatch.setattr(revision_diff, "HANDOFF_ROOT",
                        tmp_path / "_handoff")
    target = tmp_path / "takeoff_delta.md"
    target.write_text("first", encoding="utf-8")
    dir1 = revision_diff._backup_outputs([target])
    target.write_text("second", encoding="utf-8")
    dir2 = revision_diff._backup_outputs([target])
    assert dir1 and dir2 and dir1 != dir2
    assert (Path(dir1) / "takeoff_delta.md").read_text(
        encoding="utf-8") == "first"
    assert (Path(dir2) / "takeoff_delta.md").read_text(
        encoding="utf-8") == "second"


def test_cli_rejects_unknown_and_repeated_flags(tmp_path, monkeypatch,
                                                capsys,
                                                sandbox_handoff):
    old_pdf = tmp_path / "old.pdf"
    new_pdf = tmp_path / "new.pdf"
    _build_issues(old_pdf, new_pdf)

    monkeypatch.setattr(sys, "argv",
                        ["revision_diff", str(old_pdf), str(new_pdf),
                         "--out-dri", str(tmp_path)])
    assert revision_diff.main() == 1
    assert "unrecognized arguments" in capsys.readouterr().out

    monkeypatch.setattr(sys, "argv",
                        ["revision_diff", str(old_pdf), str(new_pdf),
                         "--pairs", "1:1", "--pairs", "1:1"])
    assert revision_diff.main() == 1
    assert "more than once" in capsys.readouterr().out


def test_same_file_needs_explicit_pairs(tmp_path, sandbox_handoff):
    old_pdf = tmp_path / "old.pdf"
    new_pdf = tmp_path / "new.pdf"
    _build_issues(old_pdf, new_pdf)
    with pytest.raises(ValueError, match="same file"):
        run_revision_diff(old_pdf, old_pdf, out_dir=tmp_path)


def test_diff_of_a_diff_is_refused(tmp_path, sandbox_handoff):
    import shutil

    old_pdf = tmp_path / "old.pdf"
    new_pdf = tmp_path / "new.pdf"
    _build_issues(old_pdf, new_pdf)
    relabeled = tmp_path / "new_DIFF.pdf"
    shutil.copy2(new_pdf, relabeled)
    with pytest.raises(ValueError, match="_DIFF"):
        run_revision_diff(old_pdf, relabeled, out_dir=tmp_path)


def test_rerun_backs_up_previous_outputs(tmp_path, sandbox_handoff):
    old_pdf = tmp_path / "old.pdf"
    new_pdf = tmp_path / "new.pdf"
    _build_issues(old_pdf, new_pdf)
    first = run_revision_diff(old_pdf, new_pdf, out_dir=tmp_path)
    assert first["previous_backed_up"] == ""
    second = run_revision_diff(old_pdf, new_pdf, out_dir=tmp_path)
    backup_dir = Path(second["previous_backed_up"])
    assert backup_dir.exists()
    assert (backup_dir / "new_DIFF.pdf").exists()
    assert (backup_dir / "takeoff_delta.md").exists()
    changelog = revision_diff.HANDOFF_ROOT / "changelog.md"
    assert "revision diff regenerate" in changelog.read_text(
        encoding="utf-8")
