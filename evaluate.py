"""AQUASENTINEL synthetic evaluation.

Computes confusion-matrix counts, precision, recall, and F1 using
standard Python arithmetic. Used from cli.py or directly.
"""

import csv
from pathlib import Path

from detector import detect_leaks


def binary_metrics(actual, predicted):
    actual = [bool(int(value)) for value in actual]
    predicted = [bool(value) for value in predicted]

    if len(actual) != len(predicted):
        raise ValueError("Actual and predicted lengths differ.")

    tp = sum(a and p for a, p in zip(actual, predicted))
    fp = sum((not a) and p for a, p in zip(actual, predicted))
    fn = sum(a and (not p) for a, p in zip(actual, predicted))
    tn = sum((not a) and (not p) for a, p in zip(actual, predicted))

    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = (
        2 * precision * recall / (precision + recall)
        if precision + recall else 0.0
    )

    return {
        "TP": tp,
        "FP": fp,
        "FN": fn,
        "TN": tn,
        "Precision": round(precision, 3),
        "Recall": round(recall, 3),
        "F1": round(f1, 3),
    }


def run_evaluation(
    path,
    duration=10,
    offset=0.8,
    time_aware=True,
    quiet=False,
):
    """Evaluate on a labelled CSV; returns the metrics dict."""
    if not path.exists():
        raise FileNotFoundError(
            f"{path} not found. Run python3 simulator.py first."
        )

    with path.open(newline="", encoding="utf-8-sig") as file:
        rows = list(csv.DictReader(file))

    if not rows or "actual_leak" not in rows[0]:
        raise ValueError("Evaluation CSV needs an actual_leak column.")

    result = detect_leaks(
        rows,
        threshold_offset_lpm=offset,
        sustained_minutes=duration,
        time_aware_baseline=time_aware,
    )

    metrics = binary_metrics(
        [row["actual_leak"] for row in rows],
        [row["alert"] for row in result],
    )

    if not quiet:
        print("AQUASENTINEL - synthetic test evaluation")
        print("These metrics apply only to the generated dataset.")

        for name, value in metrics.items():
            print(f"{name}: {value}")

    return metrics


def main():
    run_evaluation(Path("data/test_readings.csv"))


if __name__ == "__main__":
    main()
