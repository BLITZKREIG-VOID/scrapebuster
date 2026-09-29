import os
import json
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'backend'))

from sb.contracts import (
    Health, TrafficEvent, SessionSummary, SessionDetail, Canary,
    ExposureEvent, Dataset, Finding, CaseSummary, Case, DemoStatus
)

def export():
    models = {
        "Health": Health,
        "TrafficEvent": TrafficEvent,
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
