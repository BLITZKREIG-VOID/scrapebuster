"""Shared paths and canary definitions for canary unit tests."""

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[4]
CANARIES_YAML = REPO_ROOT / "backend" / "sb" / "canary" / "canaries.yaml"


def load_canaries() -> list[dict]:
    return yaml.safe_load(CANARIES_YAML.read_text(encoding="utf-8"))["canaries"]
