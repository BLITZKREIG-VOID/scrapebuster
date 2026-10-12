#!/usr/bin/env bash
# Grep Gate Runner for ScrapeBuster v3 Pure Layer 3 Full Offense
set -euo pipefail

TARGET="${1:-.}"
python "$(dirname "$0")/grep_gate.py" "$TARGET"
