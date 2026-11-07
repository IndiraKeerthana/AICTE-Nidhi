import pytest
from app.services.compliance_rules import ComplianceRuleEngine


def test_rules_loading_and_structure():
    engine = ComplianceRuleEngine()
    assert engine.ruleset_version is not None
    cat = engine.get_category_info("INCREASE_INTAKE")
    assert cat is not None
    assert len(cat.get("mandatory_documents", [])) >= 5

    rules = engine.get_rules_for_category("INCREASE_INTAKE")
    assert len(rules) >= 5

    rule1 = engine.get_rule_by_code("APH-2026-MANDATORY-DOCS-01")
    assert rule1 is not None
    assert rule1["severity"] == "CRITICAL"
    assert rule1["is_mandatory"] is True
    assert rule1["evaluation_method"] == "MANDATORY_DOCUMENTS"


def test_evaluate_unsupported_method():
    engine = ComplianceRuleEngine()
    fake_rule = {
        "rule_code": "TEST-UNSUPPORTED-99",
        "name": "Unsupported Check",
        "evaluation_method": "NON_EXISTENT_METHOD",
        "clause": "Fake Clause",
        "is_confirmed": True
    }
    res = engine.evaluate_rule(fake_rule, None, [])
    assert res["status"] == "NOT_EVALUATED"
    assert "not registered or supported" in res["explanation"]
    assert res["rule_code"] == "TEST-UNSUPPORTED-99"


def test_evaluate_rule_missing_method():
    engine = ComplianceRuleEngine()
    fake_rule = {
        "rule_code": "TEST-NO-METHOD-01",
        "name": "No Method Check",
        "clause": "Fake Clause"
    }
    res = engine.evaluate_rule(fake_rule, None, [])
    assert res["status"] == "NOT_EVALUATED"
    assert "no evaluation method configured" in res["explanation"]


def test_custom_evaluator_registration():
    engine = ComplianceRuleEngine()

    def my_custom_evaluator(rule, app, docs, baseline, ctx):
        return {
            "status": "PASS",
            "expected_value": "Custom Expected",
            "observed_value": "Custom Observed",
            "explanation": "Custom evaluation succeeded.",
            "requires_human_review": False
        }

    engine.register_evaluator("CUSTOM_CHECK", my_custom_evaluator)

    custom_rule = {
        "rule_code": "APH-CUSTOM-01",
        "name": "Custom Dynamic Rule",
        "evaluation_method": "CUSTOM_CHECK",
        "clause": "Custom Clause",
        "is_confirmed": True
    }
    res = engine.evaluate_rule(custom_rule, None, [])
    assert res["status"] == "PASS"
    assert res["expected_value"] == "Custom Expected"
    assert "Custom evaluation succeeded" in res["explanation"]


def test_pending_handbook_mapping_labeling():
    engine = ComplianceRuleEngine()
    unconfirmed_rule = {
        "rule_code": "APH-2026-FSR-05",
        "name": "Faculty Ratio",
        "clause": "APH Chapter VII, Clause 7.1",
        "is_confirmed": False,
        "evaluation_method": "NON_EXISTENT"
    }
    res = engine.evaluate_rule(unconfirmed_rule, None, [])
    assert "[PENDING OFFICIAL HANDBOOK MAPPING]" in res["clause"]


def test_campus_land_norm_evaluator():
    engine = ComplianceRuleEngine()
    land_rule = engine.get_rule_by_code("APH-2026-LAND-03")

    class MockAppPass:
        declared_land_acres = 8.25

    class MockAppFail:
        declared_land_acres = 1.5

    class MockAppMissing:
        declared_land_acres = None

    res_pass = engine.evaluate_rule(land_rule, MockAppPass(), [])
    assert res_pass["status"] == "PASS"

    res_fail = engine.evaluate_rule(land_rule, MockAppFail(), [])
    assert res_fail["status"] == "FAIL"

    res_miss = engine.evaluate_rule(land_rule, MockAppMissing(), [])
    assert res_miss["status"] == "NOT_ENOUGH_INFORMATION"


def test_intake_baseline_evaluator():
    engine = ComplianceRuleEngine()
    intake_rule = engine.get_rule_by_code("APH-2026-INTAKE-04")

    class MockApp:
        declared_intake = 120

    class MockBaselineMatch:
        approved_intake = 120
        academic_year = "2025-2026"

    class MockBaselineMismatch:
        approved_intake = 60
        academic_year = "2025-2026"

    res_match = engine.evaluate_rule(intake_rule, MockApp(), [], baseline=MockBaselineMatch())
    assert res_match["status"] == "PASS"

    res_mismatch = engine.evaluate_rule(intake_rule, MockApp(), [], baseline=MockBaselineMismatch())
    assert res_mismatch["status"] == "FAIL"

    res_no_base = engine.evaluate_rule(intake_rule, MockApp(), [], baseline=None)
    assert res_no_base["status"] == "NOT_ENOUGH_INFORMATION"

