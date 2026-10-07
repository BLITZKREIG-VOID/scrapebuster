#!/usr/bin/env python3
"""Grep Gate Script for ScrapeBuster v3 Pure Layer 3 Full Offense.

Scans all files and paths across the repository (including hidden, ignored, and binary files),
excluding only the .git directory.
Ensures zero forbidden tokens exist in the repository.
Validation guard terms are constructed from character code arrays to prevent self-matching.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path


# Build forbidden term byte patterns from character code arrays (zero literal forbidden strings in source)
FORBIDDEN_BYTE_PATTERNS = [
    # Term 1: [99, 97, 109, 112, 117, 115, 99, 97, 114, 116]
    bytes([99, 97, 109, 112, 117, 115, 99, 97, 114, 116]),
    # Term 2: [101, 120, 97, 109, 112, 108, 101, 99, 111, 114, 112]
    bytes([101, 120, 97, 109, 112, 108, 101, 99, 111, 114, 112]),
    # Term 3: [110, 105, 109, 98, 117, 115]
    bytes([110, 105, 109, 98, 117, 115]),
    # Term 4: [100, 101, 109, 111, 95, 115, 105, 116, 101]
    bytes([100, 101, 109, 111, 95, 115, 105, 116, 101]),
    # Term 5: [108, 97, 121, 101, 114, 49]
    bytes([108, 97, 121, 101, 114, 49]),
    # Term 6: [108, 97, 121, 101, 114, 50]
    bytes([108, 97, 121, 101, 114, 50]),
    # Term 7: [115, 98, 95, 99, 108, 101, 97, 114]
    bytes([115, 98, 95, 99, 108, 101, 97, 114]),
]


def scan_tree(root_dir: str | Path) -> list[tuple[str, str]]:
    """Scan all files and paths under root_dir for forbidden byte patterns."""
    root_path = Path(root_dir).resolve()
    violations: list[tuple[str, str]] = []

    for dirpath, dirnames, filenames in os.walk(root_path):
        parts = Path(dirpath).parts
        if ".git" in parts:
            continue

        # Check directory path names
        dir_bytes = os.path.relpath(dirpath, root_path).replace("\\", "/").lower().encode("utf-8")
        for idx, pattern in enumerate(FORBIDDEN_BYTE_PATTERNS):
            if pattern in dir_bytes:
                violations.append((dirpath, f"directory path matches rule {idx + 1}"))

        for filename in filenames:
            file_full = os.path.join(dirpath, filename)
            rel_file = os.path.relpath(file_full, root_path).replace("\\", "/")
            rel_bytes = rel_file.lower().encode("utf-8")

            # Check filename and relative path
            for idx, pattern in enumerate(FORBIDDEN_BYTE_PATTERNS):
                if pattern in rel_bytes:
                    violations.append((rel_file, f"filename/path matches rule {idx + 1}"))
                    break

            # Check file content in binary mode to prevent decode failures
            try:
                with open(file_full, "rb") as fp:
                    content = fp.read()
                content_lower = content.lower()
                for idx, pattern in enumerate(FORBIDDEN_BYTE_PATTERNS):
                    if pattern in content_lower:
                        violations.append((rel_file, f"file content matches rule {idx + 1}"))
                        break
            except Exception as exc:
                violations.append((rel_file, f"read error: {exc}"))

    return violations


def main() -> int:
    target_root = sys.argv[1] if len(sys.argv) > 1 else "."
    print(f"Running Grep Gate on: {os.path.abspath(target_root)}")
    violations = scan_tree(target_root)

    if violations:
        print(f"\nGREP GATE FAILED: Found {len(violations)} forbidden token violations:")
        for path, reason in violations:
            print(f"  - {path}: {reason}")
        return 1

    print("\nGREP GATE PASSED: Zero forbidden tokens found outside .git.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
