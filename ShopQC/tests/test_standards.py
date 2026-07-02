"""ASTM minimum reference, MTR shortfall flag, and AISC 303-22 tolerance text."""

from shopqc import standards as s


def test_astm_minimums():
    assert s.ASTM_MIN["A992"] == {"fy": 50, "fu": 65}
    assert s.ASTM_MIN["A36"] == {"fy": 36, "fu": 58}
    assert s.ASTM_MIN["A500 GR C"] == {"fy": 50, "fu": 62}
    assert s.ASTM_MIN["F1554 GR 55"] == {"fy": 55, "fu": 75}
    assert s.astm_minimum("a992") == {"fy": 50, "fu": 65}  # case insensitive
    assert s.astm_minimum("unknown") is None
    assert s.astm_minimum("") is None


def test_astm_shortfall_flags_below_minimum():
    assert s.astm_shortfall("A992", 48, 65)    # Fy below 50
    assert s.astm_shortfall("A992", 50, 60)    # Fu below 65
    assert not s.astm_shortfall("A992", 50, 65)   # exactly minimum
    assert not s.astm_shortfall("A992", 55, 70)   # above
    assert not s.astm_shortfall("A992", None, None)
    assert not s.astm_shortfall("UNKNOWN", 1, 1)  # unknown grade, nothing to check


def test_astm_reference_text():
    t = s.astm_reference_text("A992")
    assert "A992" in t and "50" in t and "65" in t
    assert s.astm_reference_text("nope") == ""


def test_aisc_tolerance_references():
    assert "AISC 303-22" in s.AISC_303_LENGTH_TOL
    assert "1/16" in s.AISC_303_LENGTH_TOL and "1/8" in s.AISC_303_LENGTH_TOL
    assert "AISC 303-22" in s.AISC_303_STRAIGHTNESS_REF
    assert "ASTM A6" in s.AISC_303_STRAIGHTNESS_REF


def test_no_em_dashes_in_reference_text():
    for txt in (s.AISC_303_LENGTH_TOL, s.AISC_303_STRAIGHTNESS_REF,
                s.astm_reference_text("A992"), s.astm_shortfall("A992", 1, 1)):
        assert chr(0x2014) not in txt and chr(0x2013) not in txt
