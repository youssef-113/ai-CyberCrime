from typing import Dict, List


def calculate_accuracy(results: List[Dict]) -> float:
    if not results:
        return 0.0

    correct = sum(
        1 for result in results
        if result.get("predicted") == result.get("expected")
    )

    return correct / len(results)


def summarize_results(results: List[Dict]) -> Dict:
    total = len(results)
    correct = sum(
        1 for result in results
        if result.get("predicted") == result.get("expected")
    )
    incorrect = total - correct

    return {
        "total": total,
        "correct": correct,
        "incorrect": incorrect,
        "accuracy": calculate_accuracy(results),
    }


def group_errors_by_expected_type(results: List[Dict]) -> Dict[str, int]:
    errors = {}

    for result in results:
        expected = result.get("expected")
        predicted = result.get("predicted")

        if expected != predicted:
            errors[expected] = errors.get(expected, 0) + 1

    return errors