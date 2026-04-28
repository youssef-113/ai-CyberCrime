
import json
from pathlib import Path

TEST_CASES_DIR = Path("data/test_cases")

def load_test_cases():
    cases = []
    for file in TEST_CASES_DIR.glob("*.json"):
        with open(file, "r", encoding="utf-8") as f:
            cases.append(json.load(f))
    return cases
