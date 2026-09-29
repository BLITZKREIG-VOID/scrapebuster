import json
import os
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'backend'))

from sb.contracts import (
    Canary,
    Case,
    CaseSummary,
    Dataset,
    DemoStatus,
    ExposureEvent,
    Finding,
    Health,
    Overview,
    PipelineStage,
    SessionList,
    SessionDetail,
    SessionSummary,
    TrafficEvent,
    TrafficEvents,
)


def export():
    models = {
        "Health": Health,
        "Overview": Overview,
        "PipelineStage": PipelineStage,
        "TrafficEvent": TrafficEvent,
        "TrafficEvents": TrafficEvents,
        "SessionList": SessionList,
        "SessionSummary": SessionSummary,
        "SessionDetail": SessionDetail,
        "Canary": Canary,
        "ExposureEvent": ExposureEvent,
        "Dataset": Dataset,
        "Finding": Finding,
        "CaseSummary": CaseSummary,
        "Case": Case,
        "DemoStatus": DemoStatus
    }
    
    out_dir = os.path.join(os.path.dirname(__file__), '..', 'contracts', 'schemas')
    os.makedirs(out_dir, exist_ok=True)
    
    for name, model in models.items():
        schema = model.model_json_schema()
        with open(os.path.join(out_dir, f"{name}.schema.json"), "w") as f:
            json.dump(schema, f, indent=2)
            
    print(f"Exported {len(models)} schemas to {out_dir}")

if __name__ == "__main__":
    export()
