"""
Seed FDR Demonstration Scenarios Script
CLI entry point to initialize or force refresh the 12 dynamic synthetic FDR scenarios.
"""

import sys
import os
from pathlib import Path

# Add backend directory to path
backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from app.database import engine, Base, SessionLocal
from app.services.baseline_service import ensure_default_users
from app.services.fdr_demo_data import seed_fdr_demo_scenarios

def main():
    force = "--force" in sys.argv or "-f" in sys.argv
    print(f"[*] Initializing Database Schema (force_refresh={force})...")
    Base.metadata.create_all(bind=engine)
    
    db = SessionLocal()
    try:
        print("[*] Ensuring baseline authentication users...")
        users = ensure_default_users(db)
        print(f"    -> Default users initialized: {[u.username for u in users]}")
        
        print("[*] Seeding 12 FDR Demonstration Scenarios...")
        results = seed_fdr_demo_scenarios(db, force_refresh=force)
        from app.models import DepositInstrument
        instruments = db.query(DepositInstrument).all()
        print(f"[+] Successfully seeded {len(instruments)} FDR records in database:")
        for r in instruments:
            print(f"    - [ID: {r.id:2d}] {r.instrument_number} | {r.lifecycle_status:18s} | {r.validity_status:14s} | {r.issuing_bank:20s}")
    except Exception as e:
        print(f"[!] Error seeding scenarios: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        db.close()

if __name__ == "__main__":
    main()
