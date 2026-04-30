import json
from pathlib import Path
from pydantic import ValidationError
from services.api.models import TestCase

data_dir = Path("data/test_cases/data")
files = list(data_dir.glob("*.json"))

print(f"Found {len(files)} files\n")

for file_path in files:
    try:
        with open(file_path, encoding="utf-8") as f:
            data = json.load(f)

        TestCase(**data)

        print(f"VALID: {file_path.name}")

    except ValidationError as e:
        print(f"INVALID: {file_path.name}")
        print(e)
        print("-" * 50)

    except Exception as e:
        print(f"ERROR: {file_path.name}")
        print(e)
        print("-" * 50)