"""Validate all representative API fixtures and enforce endpoint coverage."""
import glob
import json
import os
import sys

from pydantic import ValidationError

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "backend"))
import sb.contracts as contracts  # noqa: E402

# File stem -> canonical response model. Required entries correspond to the
# dashboard-facing GET map in the master implementation plan; additional
# action responses (verification/reset/ingest/run) are also checked.
REQUIRED_FIXTURES = {
    "Health": "Health",
    "Overview": "Overview",
    "TrafficEvents": "TrafficEvents",
    "SessionList": "SessionList",
    "SessionDetail": "SessionDetail",
    "CanariesResponse": "CanariesResponse",
    "CanaryDetail": "CanaryDetail",
    "DatasetsResponse": "DatasetsResponse",
    "ProbeListResponse": "ProbeListResponse",
    "ProbeRun": "ProbeRun",
    "CaseSummaries": "CaseSummaries",
    "Case": "Case",
    "CaseEvidenceResponse": "CaseEvidenceResponse",
    "DemoStatus": "DemoStatus",
    "EvidenceVerification": "EvidenceVerification",
    "ProbeRunResponse": "ProbeRunResponse",
    "DemoResetResponse": "DemoResetResponse",
}


def check_contracts():
    fixtures_dir = os.path.join(os.path.dirname(__file__), "..", "contracts", "fixtures")
    json_files = sorted(glob.glob(os.path.join(fixtures_dir, "*.json")))
    if not json_files:
        print("FAIL: No JSON fixtures found to validate.")
        return 1

    present = {os.path.splitext(os.path.basename(path))[0] for path in json_files}
    missing = sorted(set(REQUIRED_FIXTURES) - present)
    if missing:
        print("FAIL: Missing required response fixtures: " + ", ".join(missing))
        return 1

    failed = False
    for file_path in json_files:
        basename = os.path.basename(file_path)
        model_name = REQUIRED_FIXTURES.get(os.path.splitext(basename)[0], os.path.splitext(basename)[0])
        model = getattr(contracts, model_name, None)
        if model is None:
            print(f"FAIL: Fixture {basename} has no canonical model '{model_name}'.")
            failed = True
            continue
        try:
            with open(file_path, encoding="utf-8") as fixture_file:
                data = json.load(fixture_file)
            model.model_validate(data)
            print(f"PASS: {basename} -> {model_name}")
        except (json.JSONDecodeError, OSError) as exc:
            print(f"FAIL: Fixture {basename} is not valid JSON: {exc}")
            failed = True
        except ValidationError as exc:
            print(f"FAIL: Fixture {basename} failed validation against {model_name}:\n{exc}")
            failed = True
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(check_contracts())
