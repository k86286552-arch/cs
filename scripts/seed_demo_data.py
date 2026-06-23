"""Seed script: ensures fixture data is in place for demo mode."""
from __future__ import annotations

import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_DIR = PROJECT_ROOT / "data" / "fixtures"


def check_fixtures() -> None:
    required = ["news.json", "resources.json", "prices.csv"]
    missing = []

    for name in required:
        path = FIXTURE_DIR / name
        if not path.exists():
            missing.append(name)
        else:
            size = path.stat().st_size
            print(f"  [OK] {name} ({size} bytes)")

    if missing:
        print(f"\n  [WARN] Missing fixtures: {', '.join(missing)}")
        print("  Run the full setup to generate fixture data.")
    else:
        print("\n  All fixture data is in place.")


if __name__ == "__main__":
    print("Checking fixture data...")
    print(f"Fixture dir: {FIXTURE_DIR}\n")
    check_fixtures()
