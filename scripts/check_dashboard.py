#!/usr/bin/env python3
"""Cross-platform dashboard verification and build script.

Runs npm install, typecheck, and build inside dashboard/,
then cleans temporary artifacts (node_modules, dist) to keep repository clean.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path


def main() -> int:
    dashboard_dir = Path("dashboard")
    if not dashboard_dir.is_dir():
        print("dashboard directory not present, skipping.")
        return 0

    print("=== Checking Dashboard ===")
    try:
        # Install dependencies
        print("Running npm install in dashboard/...")
        subprocess.run(["npm", "install"], cwd=dashboard_dir, shell=True, check=True)

        # Run typecheck
        print("Running npm run typecheck in dashboard/...")
        subprocess.run(["npm", "run", "typecheck"], cwd=dashboard_dir, shell=True, check=True)

        # Run production build
        print("Running npm run build in dashboard/...")
        subprocess.run(["npm", "run", "build"], cwd=dashboard_dir, shell=True, check=True)

        print("Dashboard build and typecheck succeeded!")
        return 0
    finally:
        # Always clean node_modules and dist post-build to prevent grep gate collisions
        print("Cleaning dashboard/node_modules and dashboard/dist...")
        shutil.rmtree(dashboard_dir / "node_modules", ignore_errors=True)
        shutil.rmtree(dashboard_dir / "dist", ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
