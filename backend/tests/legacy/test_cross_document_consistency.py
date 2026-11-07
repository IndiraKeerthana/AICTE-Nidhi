import pytest
from app.services.cross_document_engine import (
    parse_land_area_to_acres,
    compare_land_areas,
    compare_institution_names,
    compare_locations,
    compare_intake_capacities,
    compare_reference_numbers,
    run_cross_document_consistency_checks
)


def test_parse_land_area_units():
    # Acres
    a, u = parse_land_area_to_acres("8.25 acres")
    assert a == pytest.approx(8.25)
    assert u == "acres"

    # Hectares (1 ha ~ 2.471 acres)
    a, u = parse_land_area_to_acres("2.0 hectares")
    assert a == pytest.approx(2.0 / 0.404686, rel=1e-2)
    assert u == "hectares"

    # Square meters (40468.56 sq m ~ 10 acres)
    a, u = parse_land_area_to_acres("40468.56 sq meters")
    assert a == pytest.approx(10.0, rel=1e-2)
    assert u == "sq. meters"

    # Square feet (43560 sq ft = 1 acre)
    a, u = parse_land_area_to_acres("87120 sq. ft")
    assert a == pytest.approx(2.0, rel=1e-2)
    assert u == "sq. feet"

    # Unparseable
    a, u = parse_land_area_to_acres("invalid land area text")
    assert a is None


def test_compare_land_areas_matching_with_conversion():
    # 5 acres vs 20234.3 sq meters (equivalent within tolerance)
    res = compare_land_areas("5.0 acres", "20234.3 sq. meters")
    assert res["status"] == "MATCH"
    assert "reconcile consistently" in res["explanation"]


def test_compare_land_areas_mismatch():
    # 8.25 acres vs 4.0 acres
    res = compare_land_areas("8.25 acres", "4.0 acres")
    assert res["status"] == "MISMATCH"
    assert "Land area discrepancy detected" in res["explanation"]
    assert res["diff_pct"] > 3.0


def test_compare_land_areas_missing():
    res = compare_land_areas(None, "5.0 acres")
    assert res["status"] == "NOT_ENOUGH_INFORMATION"


def test_compare_institution_names_abbreviations():
    # Abbreviation matching
    res = compare_institution_names(
        "Govt. Engg. College, Pune",
        "Government Engineering College, Pune"
    )
    assert res["status"] == "MATCH"
    assert res["similarity_score"] >= 75.0


def test_compare_institution_names_mismatch():
    res = compare_institution_names(
        "Sample Institute of Technology",
        "Maharashtra Technical Academy"
    )
    assert res["status"] == "MISMATCH"
    assert res["similarity_score"] < 75.0


def test_compare_institution_names_missing():
    res = compare_institution_names("", "Sample Institute")
    assert res["status"] == "NOT_ENOUGH_INFORMATION"


def test_compare_locations_matching():
    res = compare_locations(
        "Survey 104/2A, Kothrud, Pune, Maharashtra",
        "Plot 12, Kothrud Campus, Pune, Maharashtra"
    )
    assert res["status"] == "MATCH"


def test_compare_locations_mismatch():
    res = compare_locations(
        "Survey 104/2A, Kothrud, Pune, Maharashtra",
        "Plot 45, Sector 9, Hadapsar Industrial Area, Pune, Maharashtra"
    )
    assert res["status"] == "MISMATCH"
    assert "Distinct municipal campus localities" in res["explanation"] or "Location discrepancy" in res["explanation"]


def test_compare_locations_missing():
    res = compare_locations(None, "Kothrud, Pune")
    assert res["status"] == "NOT_ENOUGH_INFORMATION"


def test_compare_intake_capacities():
    res_match = compare_intake_capacities("120 seats", "120")
    assert res_match["status"] == "MATCH"
    assert res_match["intake_1"] == 120

    res_mismatch = compare_intake_capacities("60 seats", "120 seats")
    assert res_mismatch["status"] == "MISMATCH"

    res_none = compare_intake_capacities(None, "60")
    assert res_none["status"] == "NOT_ENOUGH_INFORMATION"


def test_compare_reference_numbers():
    assert compare_reference_numbers("FS-2026-1044", "fs/2026/1044")["status"] == "MATCH"
    assert compare_reference_numbers("FS-2026-1044", "BP-2025-9981")["status"] == "MISMATCH"
    assert compare_reference_numbers(None, "FS-2026-1044")["status"] == "NOT_ENOUGH_INFORMATION"


def test_run_cross_document_consistency_checks_mock():
    # Mock Document and ExtractedField
    class MockField:
        def __init__(self, key, val, page=1, conf=0.95):
            self.field_key = key
            self.field_value = val
            self.normalized_value = val
            self.page_number = page
            self.confidence_score = conf

    class MockDoc:
        def __init__(self, id, cat, filename, fields, text=""):
            self.id = id
            self.document_category = cat
            self.original_filename = filename
            self.status = "PROCESSED"
            self.extracted_fields = fields
            self.extracted_text = text

    class MockInst:
        name = "Sample Institute of Technology"
        address = "Survey 104/2A, Kothrud"
        district = "Pune"
        state = "Maharashtra"

    class MockApp:
        institution = MockInst()
        declared_land_acres = 8.25
        declared_intake = 120

    doc_land = MockDoc(1, "LAND_TITLE_DEED", "title_deed.pdf", [MockField("land_area", "8.25 acres")], "Sample Institute of Technology Survey 104/2A Kothrud Pune")
    doc_bp = MockDoc(2, "BUILDING_PLAN", "building_plan.pdf", [MockField("land_area", "8.25 acres")], "Sample Institute of Technology Survey 104/2A Kothrud Pune")
    doc_affil = MockDoc(3, "AFFILIATION_LETTER", "affiliation.pdf", [MockField("intake_capacity", "120")], "Sample Institute of Technology approved intake 120 seats")

    results = run_cross_document_consistency_checks(MockApp(), [doc_land, doc_bp, doc_affil])

    # Should have checks for land area (deed vs bp), land area (deed vs declared), institution names, intake, and location
    assert len(results) >= 4
    check_codes = [r["check_code"] for r in results]
    assert "XDOC-LAND-DEED-BP" in check_codes
    assert "XDOC-LAND-DEED-DECLARED" in check_codes
    assert "XDOC-INTAKE-AFFIL-DECLARED" in check_codes

    # Land area should match
    land_bp_check = next(r for r in results if r["check_code"] == "XDOC-LAND-DEED-BP")
    assert land_bp_check["status"] == "MATCH"

