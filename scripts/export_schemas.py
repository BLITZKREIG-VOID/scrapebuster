import json
import os
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "backend"))
from sb import contracts


def export():
    names = [
        "Health",
        "TrafficEvent",
        "TrafficEvents",
        "SessionSummary",
        "SessionDetail",
        "SessionList",
        "PipelineStage",
        "DecisionCounts",
        "LadderCounts",
        "CanaryCounts",
        "CaseCounts",
        "Overview",
        "ExposureEvent",
        "Canary",
        "Publication",
        "CanaryDetail",
        "CanariesResponse",
        "Dataset",
        "DatasetsResponse",
        "ProbeResult",
        "ProbeRun",
        "ProbeListResponse",
        "ProbeRunResponse",
        "Finding",
        "CaseSummary",
        "Case",
        "CaseSummaries",
        "EvidenceFile",
        "EvidenceManifest",
        "EvidenceObject",
        "CaseEvidenceResponse",
        "EvidenceCheck",
        "EvidenceVerification",
        "DemoStep",
        "DemoStatus",
        "DemoResetCheck",
        "DemoResetResponse",
    ]
    out_dir = os.path.join(os.path.dirname(__file__), "..", "contracts", "schemas")
    os.makedirs(out_dir, exist_ok=True)
    for name in names:
        model = getattr(contracts, name)
        with open(os.path.join(out_dir, f"{name}.schema.json"), "w", encoding="utf-8") as f:
            json.dump(model.model_json_schema(), f, indent=2)
            f.write("\n")
    print(f"Exported {len(names)} schemas to {out_dir}")


if __name__ == "__main__":
    export()
