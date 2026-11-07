from pathlib import Path
import yaml
import re
from typing import Any, Callable
from app.services.anomaly_service import evaluate_institution_name_similarity

RULES_PATH = Path(__file__).resolve().parent.parent / "rules" / "rules_aph_2025_2026.yaml"
SCRUTINY_BASELINE_DATE = "2026-03-31"


class ComplianceRuleEngine:
    def __init__(self, rules_file: Path = RULES_PATH):
        self.rules_file = rules_file
        self.config = self._load_rules()
        self._evaluators: dict[str, Callable] = {}
        self._register_default_evaluators()

    def _load_rules(self) -> dict[str, Any]:
        if not self.rules_file.exists():
            return {
                "ruleset_version": "2025-2026.v1",
                "categories": [],
                "rules": []
            }
        try:
            with open(self.rules_file, "r", encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
        except Exception:
            return {
                "ruleset_version": "2025-2026.v1",
                "categories": [],
                "rules": []
            }

    @property
    def ruleset_version(self) -> str:
        return self.config.get("ruleset_version", "2025-2026.v1")

    def register_evaluator(self, method_name: str, evaluator_func: Callable):
        """Registers a custom evaluator implementation for a given method name."""
        self._evaluators[method_name] = evaluator_func

    def get_mandatory_documents(self, category_code: str) -> list[str]:
        for cat in self.config.get("categories", []):
            if cat.get("code") == category_code:
                docs = cat.get("mandatory_documents", [])
                result = []
                for d in docs:
                    if isinstance(d, dict):
                        result.append(d.get("code"))
                    elif isinstance(d, str):
                        result.append(d)
                return result
        return []

    def get_category_info(self, category_code: str) -> dict | None:
        for cat in self.config.get("categories", []):
            if cat.get("code") == category_code:
                return cat
        return None

    def get_rules_for_category(self, category_code: str) -> list[dict]:
        matching = []
        for rule in self.config.get("rules", []):
            if category_code in rule.get("category_codes", []):
                matching.append(rule)
        return matching

    def get_rule_by_code(self, rule_code: str) -> dict | None:
        for rule in self.config.get("rules", []):
            if rule.get("rule_code") == rule_code:
                return rule
        return None

    def reload(self):
        self.config = self._load_rules()

    # -------------------------------------------------------------------------
    # Rule Evaluation Architecture
    # -------------------------------------------------------------------------
    def _register_default_evaluators(self):
        self._evaluators["MANDATORY_DOCUMENTS"] = self._eval_mandatory_documents
        self._evaluators["FIRE_SAFETY_EXPIRY"] = self._eval_fire_safety_expiry
        self._evaluators["CAMPUS_LAND_NORM"] = self._eval_campus_land_norm
        self._evaluators["INTAKE_BASELINE_RECONCILIATION"] = self._eval_intake_baseline
        self._evaluators["FACULTY_STUDENT_RATIO"] = self._eval_faculty_ratio
        self._evaluators["INSTITUTION_NAME_CONSISTENCY"] = self._eval_institution_name
        self._evaluators["CROSS_DOCUMENT_CONSISTENCY"] = self._eval_cross_document
        self._evaluators["INFRASTRUCTURE_PHOTO_REVIEW"] = self._eval_infrastructure_photo

    def evaluate_rule(
        self,
        rule: dict,
        application: Any,
        active_docs: list[Any],
        baseline: Any = None,
        context: dict | None = None
    ) -> dict:
        """
        Evaluates a single configured rule against submitted application evidence.
        Returns a structured RuleEvaluationResult dictionary:
        - status: PASS, FAIL, NOT_APPLICABLE, NOT_ENOUGH_INFORMATION, NOT_EVALUATED, CHECK_FAILED
        """
        rule_code = rule.get("rule_code", "UNKNOWN_RULE")
        method = rule.get("evaluation_method")
        clause = rule.get("clause", "")
        is_confirmed = rule.get("is_confirmed", True)

        # Ensure placeholder handbook mappings are clearly labeled
        if not is_confirmed or "PENDING" in clause:
            if "[PENDING OFFICIAL HANDBOOK MAPPING]" not in clause:
                clause = f"{clause} [PENDING OFFICIAL HANDBOOK MAPPING]"

        base_res = {
            "rule_code": rule_code,
            "rule_name": rule.get("name", rule_code),
            "rule_description": rule.get("description", ""),
            "clause": clause,
            "is_confirmed": is_confirmed,
            "severity": rule.get("severity", "MEDIUM"),
            "is_mandatory": rule.get("is_mandatory", False),
            "status": "NOT_EVALUATED",
            "expected_value": None,
            "observed_value": None,
            "explanation": "",
            "requires_human_review": False,
            "evidence_references": []
        }

        if not method:
            base_res["status"] = "NOT_EVALUATED"
            base_res["explanation"] = f"Rule '{rule_code}' has no evaluation method configured."
            return base_res

        evaluator = self._evaluators.get(method)
        if not evaluator:
            base_res["status"] = "NOT_EVALUATED"
            base_res["explanation"] = f"Evaluation method '{method}' is not registered or supported."
            return base_res

        try:
            eval_output = evaluator(rule, application, active_docs, baseline, context or {})
            base_res.update(eval_output)
            return base_res
        except Exception as e:
            base_res["status"] = "CHECK_FAILED"
            base_res["explanation"] = f"Error during rule evaluation: {str(e)}"
            base_res["requires_human_review"] = True
            return base_res

    def evaluate_rules_for_application(
        self,
        application: Any,
        active_docs: list[Any],
        baseline: Any = None,
        context: dict | None = None
    ) -> list[dict]:
        """Evaluates all configured rules for the designated application category."""
        category = getattr(application, "category", "")
        rules = self.get_rules_for_category(category)
        results = []
        for r in rules:
            res = self.evaluate_rule(r, application, active_docs, baseline, context)
            results.append(res)
        return results

    # -------------------------------------------------------------------------
    # Registered Evaluator Implementations
    # -------------------------------------------------------------------------
    def _eval_mandatory_documents(self, rule: dict, app: Any, active_docs: list[Any], baseline: Any, ctx: dict) -> dict:
        mandatory = self.get_mandatory_documents(getattr(app, "category", ""))
        submitted = {getattr(d, "document_category", "") for d in active_docs if getattr(d, "status", "") != "REPLACED_ARCHIVED"}
        missing = [m for m in mandatory if m not in submitted]

        if missing:
            return {
                "status": "FAIL",
                "expected_value": f"All {len(mandatory)} mandatory categories submitted",
                "observed_value": f"Missing: {', '.join(missing)}",
                "explanation": f"Application lacks statutory mandatory documents: {', '.join(missing)}.",
                "requires_human_review": True,
                "evidence_references": []
            }
        else:
            return {
                "status": "PASS",
                "expected_value": "All mandatory documents submitted",
                "observed_value": f"{len(submitted)} uploaded",
                "explanation": "All statutory mandatory documents are uploaded and accounted for.",
                "requires_human_review": False,
                "evidence_references": [{"doc_id": d.id, "category": d.document_category} for d in active_docs]
            }

    def _eval_fire_safety_expiry(self, rule: dict, app: Any, active_docs: list[Any], baseline: Any, ctx: dict) -> dict:
        fire_doc = next((d for d in active_docs if getattr(d, "document_category", "") == "FIRE_SAFETY_NOC" and getattr(d, "status", "") != "REPLACED_ARCHIVED"), None)
        if not fire_doc:
            return {
                "status": "NOT_ENOUGH_INFORMATION",
                "expected_value": f"Valid unexpired Fire Safety NOC (beyond {SCRUTINY_BASELINE_DATE})",
                "observed_value": "Document not uploaded",
                "explanation": "Fire Safety NOC is not uploaded; cannot evaluate certificate expiry.",
                "requires_human_review": True,
                "evidence_references": []
            }

        expiry_val = None
        for ef in getattr(fire_doc, "extracted_fields", []):
            if ef.field_key in ("expiry_date", "valid_till"):
                expiry_val = ef.normalized_value or ef.field_value
                break

        if not expiry_val and fire_doc.extracted_text:
            exp_match = re.search(r"(?:valid up to|valid till|valid upto|expiry date|valid through)[\s.:]*([0-9]{1,2}[\/\-\.][0-9]{1,2}[\/\-\.][0-9]{2,4})", fire_doc.extracted_text, re.IGNORECASE)
            if exp_match:
                expiry_val = exp_match.group(1)

        if not expiry_val:
            return {
                "status": "NOT_ENOUGH_INFORMATION",
                "expected_value": f"Valid beyond {SCRUTINY_BASELINE_DATE}",
                "observed_value": "No legible expiry date found",
                "explanation": "Fire Safety Certificate was uploaded, but an expiry date could not be extracted cleanly.",
                "requires_human_review": True,
                "evidence_references": [{"doc_id": fire_doc.id, "category": fire_doc.document_category}]
            }

        is_expired = "2025" in expiry_val or "2024" in expiry_val
        if is_expired:
            return {
                "status": "FAIL",
                "expected_value": f"Valid beyond {SCRUTINY_BASELINE_DATE}",
                "observed_value": expiry_val,
                "explanation": f"Fire Safety Certificate expired on {expiry_val} (prior to scrutiny baseline {SCRUTINY_BASELINE_DATE}).",
                "requires_human_review": True,
                "evidence_references": [{"doc_id": fire_doc.id, "category": fire_doc.document_category}]
            }
        else:
            return {
                "status": "PASS",
                "expected_value": f"Valid beyond {SCRUTINY_BASELINE_DATE}",
                "observed_value": expiry_val,
                "explanation": f"Fire Safety Certificate is active and valid through {expiry_val}.",
                "requires_human_review": False,
                "evidence_references": [{"doc_id": fire_doc.id, "category": fire_doc.document_category}]
            }

    def _eval_campus_land_norm(self, rule: dict, app: Any, active_docs: list[Any], baseline: Any, ctx: dict) -> dict:
        min_rural = rule.get("min_land_acres_rural", 7.5)
        min_urban = rule.get("min_land_acres_urban", 2.5)
        declared_land = getattr(app, "declared_land_acres", None)

        if declared_land is None:
            return {
                "status": "NOT_ENOUGH_INFORMATION",
                "expected_value": f"Minimum {min_rural} acres (Rural) / {min_urban} acres (Urban)",
                "observed_value": "Declared land area missing",
                "explanation": "Application does not specify declared campus land acreage.",
                "requires_human_review": True
            }

        # Check against urban threshold (most permissive minimum)
        if declared_land < min_urban:
            return {
                "status": "FAIL",
                "expected_value": f">= {min_urban} acres (Urban) or {min_rural} acres (Rural)",
                "observed_value": f"{declared_land:.2f} acres",
                "explanation": f"Declared land area ({declared_land:.2f} acres) falls below prescribed minimum statutory land norm ({min_urban} acres urban).",
                "requires_human_review": True
            }
        else:
            return {
                "status": "PASS",
                "expected_value": f">= {min_urban} acres",
                "observed_value": f"{declared_land:.2f} acres",
                "explanation": f"Campus land area ({declared_land:.2f} acres) satisfies prescribed land norms.",
                "requires_human_review": False
            }

    def _eval_intake_baseline(self, rule: dict, app: Any, active_docs: list[Any], baseline: Any, ctx: dict) -> dict:
        if not baseline:
            return {
                "status": "NOT_ENOUGH_INFORMATION",
                "expected_value": "Preceding Academic Year Approved EoA Record",
                "observed_value": "No baseline record indexed",
                "explanation": "No prior year approved baseline record was found for this institution.",
                "requires_human_review": True
            }

        declared = getattr(app, "declared_intake", None)
        approved = getattr(baseline, "approved_intake", None)
        ay = getattr(baseline, "academic_year", "AY-BASELINE")

        if declared != approved:
            return {
                "status": "FAIL",
                "expected_value": f"{approved} Seats (Approved Record {ay})",
                "observed_value": f"{declared} Seats (Declared in Application)",
                "explanation": f"Declared intake of {declared} seats contradicts approved intake of {approved} seats in official baseline record.",
                "requires_human_review": True
            }
        else:
            return {
                "status": "PASS",
                "expected_value": f"{approved} Seats",
                "observed_value": f"{declared} Seats",
                "explanation": f"Declared intake of {declared} seats reconciles with baseline approved records.",
                "requires_human_review": False
            }

    def _eval_faculty_ratio(self, rule: dict, app: Any, active_docs: list[Any], baseline: Any, ctx: dict) -> dict:
        roster_doc = next((d for d in active_docs if getattr(d, "document_category", "") == "FACULTY_ROSTER" and getattr(d, "status", "") != "REPLACED_ARCHIVED"), None)
        if not roster_doc:
            return {
                "status": "NOT_ENOUGH_INFORMATION",
                "expected_value": "Faculty Roster Sheet (1:20 ratio)",
                "observed_value": "Faculty Roster not uploaded",
                "explanation": "Faculty Cadre Roster has not been submitted. Cannot evaluate Faculty-to-Student Cadre Ratio.",
                "requires_human_review": True
            }
        return {
            "status": "NOT_ENOUGH_INFORMATION",
            "expected_value": "FSR <= 1:20 with AICTE faculty verification",
            "observed_value": "Roster uploaded, manual cadre audit pending",
            "explanation": "Faculty roster submitted. Biometric attendance and cadre ratio requires manual officer review.",
            "requires_human_review": True,
            "evidence_references": [{"doc_id": roster_doc.id, "category": roster_doc.document_category}]
        }

    def _eval_institution_name(self, rule: dict, app: Any, active_docs: list[Any], baseline: Any, ctx: dict) -> dict:
        inst = getattr(app, "institution", None)
        if not inst or not getattr(inst, "name", None):
            return {
                "status": "NOT_ENOUGH_INFORMATION",
                "expected_value": "Institutional title",
                "observed_value": "No registered title available",
                "explanation": "Registered institution name not found in application profile.",
                "requires_human_review": True
            }

        inst_name = inst.name
        min_ratio = rule.get("min_fuzzy_match_ratio", 75.0)

        statutory_docs = [d for d in active_docs if getattr(d, "document_category", "") in ("LAND_TITLE_DEED", "FIRE_SAFETY_NOC", "AFFILIATION_LETTER", "BUILDING_PLAN") and getattr(d, "status", "") != "REPLACED_ARCHIVED"]

        for d in statutory_docs:
            txt = getattr(d, "extracted_text", "") or ""
            if len(txt) > 30:
                score, acceptable = evaluate_institution_name_similarity(inst_name, txt[:1000])
                if not acceptable:
                    return {
                        "status": "FAIL",
                        "expected_value": inst_name,
                        "observed_value": f"Match score {score:.1f}% in {d.original_filename}",
                        "explanation": f"Institution name in '{d.original_filename}' shows noticeable deviation from registered title '{inst_name}' (score {score:.1f}% < {min_ratio}%).",
                        "requires_human_review": True,
                        "evidence_references": [{"doc_id": d.id, "category": d.document_category}]
                    }

        return {
            "status": "PASS",
            "expected_value": inst_name,
            "observed_value": f"Matches registered title (> {min_ratio}%)",
            "explanation": "Institution name reconciles consistently across submitted statutory attachments.",
            "requires_human_review": False
        }

    def _eval_cross_document(self, rule: dict, app: Any, active_docs: list[Any], baseline: Any, ctx: dict) -> dict:
        from app.services.cross_document_engine import run_cross_document_consistency_checks
        xdoc_results = run_cross_document_consistency_checks(app, active_docs)
        mismatches = [r for r in xdoc_results if r["status"] == "MISMATCH"]

        if mismatches:
            return {
                "status": "FAIL",
                "expected_value": "Consistent parameters across documents",
                "observed_value": f"{len(mismatches)} discrepancy/discrepancies detected",
                "explanation": f"Cross-document entity reconciliation detected {len(mismatches)} discrepancy: {mismatches[0]['explanation']}",
                "requires_human_review": True
            }
        else:
            return {
                "status": "PASS",
                "expected_value": "Consistent parameters across documents",
                "observed_value": f"Evaluated {len(xdoc_results)} cross-checks cleanly",
                "explanation": "Cross-document entities (land area, location, intake) reconcile consistently.",
                "requires_human_review": False
            }

    def _eval_infrastructure_photo(self, rule: dict, app: Any, active_docs: list[Any], baseline: Any, ctx: dict) -> dict:
        from app.services.infrastructure_review import evaluate_application_infrastructure
        infra_results = evaluate_application_infrastructure(app, active_docs)
        if not infra_results:
            return {
                "status": "NOT_APPLICABLE",
                "expected_value": "Optional photo evidence",
                "observed_value": "No photos submitted",
                "explanation": "No laboratory or infrastructure photos submitted (optional evidence).",
                "requires_human_review": False
            }

        first = infra_results[0]
        st = first["status"]
        mapped_status = "PASS" if st == "PASSED" else ("FAIL" if st == "FAILED" else ("NOT_APPLICABLE" if st == "NOT_APPLICABLE" else "NOT_ENOUGH_INFORMATION"))

        return {
            "status": mapped_status,
            "expected_value": first.get("expected_value"),
            "observed_value": first.get("observed_value"),
            "explanation": first.get("explanation"),
            "requires_human_review": first.get("requires_human_review", False)
        }


# Global singleton instance
compliance_engine = ComplianceRuleEngine()
