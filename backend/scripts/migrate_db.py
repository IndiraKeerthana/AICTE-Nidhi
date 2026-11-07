"""
AICTE NIDHI Database Migration Script
Inspects SQLite verifyai.db and dynamically adds missing columns to match current models.
"""
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "verifyai.db"

def migrate():
    if not DB_PATH.exists():
        print(f"Database {DB_PATH} does not exist yet. It will be created fresh by init_db().")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    columns_to_add = {
        "applications": [
            ("tracking_id", "TEXT"),
            ("correlation_id", "TEXT"),
            ("idempotency_key", "TEXT"),
            ("category", "TEXT DEFAULT 'INCREASE_INTAKE'"),
            ("academic_year", "TEXT DEFAULT '2026-2027'"),
            ("declared_programme", "TEXT DEFAULT 'ENGINEERING_AND_TECHNOLOGY'"),
            ("declared_course", "TEXT DEFAULT 'Computer Science & Engineering'"),
            ("declared_intake", "INTEGER DEFAULT 120"),
            ("declared_land_acres", "REAL DEFAULT 8.25"),
            ("final_decision", "TEXT"),
            ("decision_remarks", "TEXT"),
            ("decided_by", "TEXT"),
            ("decided_at", "DATETIME")
        ],
        "documents": [
            ("phash_value", "TEXT"),
            ("pdf_metadata_json", "TEXT"),
            ("incremental_updates_count", "INTEGER DEFAULT 0"),
            ("ocr_needed", "BOOLEAN DEFAULT 0"),
            ("ocr_performed", "BOOLEAN DEFAULT 0"),
            ("ocr_engine_available", "BOOLEAN DEFAULT 1"),
            ("page_count", "INTEGER DEFAULT 1"),
            ("extracted_text", "TEXT")
        ],
        "extracted_fields": [
            ("normalized_value", "TEXT"),
            ("confidence_score", "REAL DEFAULT 1.0"),
            ("page_number", "INTEGER DEFAULT 1"),
            ("source_snippet", "TEXT"),
            ("bounding_box", "TEXT"),
            ("extraction_method", "TEXT DEFAULT 'PYMUPDF'")
        ],
        "check_results": [
            ("scrutiny_run_id", "INTEGER"),
            ("check_code", "TEXT"),
            ("check_name", "TEXT"),
            ("rule_id", "TEXT"),
            ("rule_version", "TEXT DEFAULT '1.0'"),
            ("category", "TEXT DEFAULT 'COMPLIANCE'"),
            ("status", "TEXT DEFAULT 'PASSED'"),
            ("expected_value", "TEXT"),
            ("observed_value", "TEXT"),
            ("explanation", "TEXT"),
            ("severity", "TEXT DEFAULT 'MEDIUM'"),
            ("requires_human_review", "BOOLEAN DEFAULT 0")
        ],
        "authority_verifications": [
            ("application_id", "INTEGER"),
            ("document_id", "INTEGER"),
            ("verification_type", "TEXT"),
            ("source_name", "TEXT"),
            ("source_reference", "TEXT"),
            ("status", "TEXT"),
            ("is_simulated", "BOOLEAN DEFAULT 1"),
            ("verified_data_json", "TEXT"),
            ("requires_human_review", "BOOLEAN DEFAULT 0"),
            ("notes", "TEXT")
        ],
        "scrutiny_runs": [
            ("ruleset_version", "TEXT DEFAULT '2025-2026.v1'"),
            ("total_checks", "INTEGER DEFAULT 0"),
            ("passed_checks", "INTEGER DEFAULT 0"),
            ("failed_checks", "INTEGER DEFAULT 0"),
            ("warnings_count", "INTEGER DEFAULT 0"),
            ("execution_duration_ms", "INTEGER DEFAULT 0"),
            ("summary_notes", "TEXT"),
            ("completed_at", "DATETIME")
        ],
        "findings": [
            ("finding_code", "TEXT"),
            ("scrutiny_run_id", "INTEGER"),
            ("check_code", "TEXT"),
            ("finding_type", "TEXT DEFAULT 'DISCREPANCY'"),
            ("category", "TEXT DEFAULT 'INTELLIGENCE'"),
            ("title", "TEXT"),
            ("description", "TEXT"),
            ("explanation", "TEXT"),
            ("severity", "TEXT DEFAULT 'MEDIUM'"),
            ("status", "TEXT DEFAULT 'OPEN'"),
            ("expected_value", "TEXT"),
            ("observed_value", "TEXT"),
            ("supporting_document_id", "INTEGER"),
            ("supporting_page_number", "INTEGER"),
            ("source_document_id", "INTEGER"),
            ("page_number", "INTEGER"),
            ("source_snippet", "TEXT"),
            ("bounding_box", "TEXT"),
            ("institutional_record_ref", "TEXT"),
            ("rule_code", "TEXT"),
            ("rule_description", "TEXT"),
            ("rule_or_detector_id", "TEXT"),
            ("rule_version", "TEXT DEFAULT '1.0'"),
            ("verification_source", "TEXT"),
            ("evidence_classification", "TEXT DEFAULT 'AUTOMATED_INFERENCE'"),
            ("recommended_action", "TEXT"),
            ("review_status", "TEXT DEFAULT 'OPEN'"),
            ("resolution_notes", "TEXT"),
            ("is_simulated", "BOOLEAN DEFAULT 0"),
            ("requires_human_review", "BOOLEAN DEFAULT 1")
        ],
        "alerts": [
            ("application_id", "INTEGER"),
            ("alert_type", "TEXT"),
            ("title", "TEXT"),
            ("message", "TEXT"),
            ("severity", "TEXT DEFAULT 'HIGH'"),
            ("status", "TEXT DEFAULT 'ACTIVE'"),
            ("acknowledged_by", "TEXT"),
            ("acknowledged_at", "DATETIME")
        ]
    }

    for table, cols in columns_to_add.items():
        # Check if table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,))
        if not cursor.fetchone():
            continue

        # Get existing columns
        cursor.execute(f"PRAGMA table_info({table})")
        existing_cols = {row[1] for row in cursor.fetchall()}

        for col_name, col_type in cols:
            if col_name not in existing_cols:
                print(f"Adding missing column {col_name} to table {table}...")
                try:
                    cursor.execute(f"ALTER TABLE {table} ADD COLUMN {col_name} {col_type}")
                except Exception as e:
                    print(f"Could not add {col_name} to {table}: {e}")

    conn.commit()
    conn.close()
    print("Database migration check completed.")

if __name__ == "__main__":
    migrate()
