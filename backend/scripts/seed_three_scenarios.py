#!/usr/bin/env python3
"""
Seed script to create or refresh the three realistic demonstration scenarios
for the AICTE NIDHI scrutiny and approval workflow:
1. APP-2026-SARASWATI-001: Complete submission, Ready for Approval.
2. APP-2026-PRAGATI-002: Missing mandatory documents.
3. APP-2026-VANGUARD-003: Submitted documents flagged for review.
"""

import sys
import logging
from pathlib import Path

# Add backend directory to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from app.database import SessionLocal
from app.services.demo_scenarios import seed_three_demo_scenarios
from app.api.decision import validate_approval_eligibility

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("seed_three_scenarios")

def main():
    logger.info("Initializing seeding of three demonstration scenarios...")
    db = SessionLocal()
    try:
        scenarios = seed_three_demo_scenarios(db=db, force_refresh=True)
        print("\n" + "=" * 70)
        print("AICTE NIDHI DEMONSTRATION SCENARIOS SEEDING SUMMARY")
        print("=" * 70)

        for app_num, app in scenarios.items():
            reasons = validate_approval_eligibility(app, db)
            is_eligible = len(reasons) == 0
            print(f"\nScenario: {app_num}")
            print(f"  Institution:        {app.institution.name} ({app.institution.aicte_permanent_id})")
            print(f"  Category:           {app.category}")
            print(f"  Submitted At (UTC): {app.created_at}")
            print(f"  Overall Status:     {app.status}")
            print(f"  Documents Uploaded: {len(app.documents)}")
            print(f"  Total Findings:     {len(app.findings)}")
            print(f"  Approval Eligible:  {'YES (Ready for Review)' if is_eligible else 'NO (Blocked)'}")
            if reasons:
                print("  Blocking Reasons:")
                for r in reasons:
                    print(f"    - {r}")
            else:
                print("  Blocking Reasons:   None (All statutory checks satisfied)")

        print("\n" + "=" * 70)
        logger.info("Seeding completed successfully.")
    except Exception as e:
        logger.error(f"Error during seeding: {e}", exc_info=True)
        sys.exit(1)
    finally:
        db.close()

if __name__ == "__main__":
    main()

