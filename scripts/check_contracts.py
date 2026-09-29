import glob
import json
import os
import sys

from pydantic import ValidationError

# Add backend to path to import sb.contracts
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'backend'))

try:
    import sb.contracts
except ImportError as e:
    print(f"Error importing contracts: {e}")
    sys.exit(1)


def check_contracts():
    fixtures_dir = os.path.join(os.path.dirname(__file__), '..', 'contracts', 'fixtures')
    json_files = glob.glob(os.path.join(fixtures_dir, '*.json'))

    if not json_files:
        print("No JSON fixtures found to validate.")
        return 0

    has_errors = False

    for file_path in json_files:
        basename = os.path.basename(file_path)
        model_name = basename.replace('.json', '')

        # Check if the model exists in sb.contracts
        model_class = getattr(sb.contracts, model_name, None)
        if not model_class:
            print(f"FAIL: Fixture {basename} has no matching model '{model_name}' in sb.contracts.")
            has_errors = True
            continue

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            print(f"FAIL: Fixture {basename} is not valid JSON: {e}")
            has_errors = True
            continue

        try:
            if isinstance(data, list):
                for item in data:
                    model_class(**item)
            else:
                model_class(**data)
            print(f"PASS: {basename}")
        except ValidationError as e:
            print(f"FAIL: Fixture {basename} failed validation against {model_name}:\n{e}")
            has_errors = True

    return 1 if has_errors else 0


if __name__ == "__main__":
    sys.exit(check_contracts())
