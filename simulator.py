"""AQUASENTINEL simulator.

Generates one-minute flow readings for 24 hours, including normal
usage, a short burst, and two sustained abnormal-flow events.
The synthetic labels are used to test the program, not to prove
real-world accuracy.

Standard library only. No external dependencies.
"""

import csv
import random
from datetime import datetime, timedelta
from pathlib import Path

DATA_DIR = Path("data")
START = datetime(2026, 10, 25, 0, 0)

FIELDNAMES = ["timestamp", "flow_lpm", "actual_leak"]


def generate_readings(seed=42):
    rng = random.Random(seed)
    rows = []

    for minute in range(1440):
        timestamp = START + timedelta(minutes=minute)
        hour = timestamp.hour

        if 0 <= hour < 5:
            expected = 0.2
        elif 6 <= hour < 9:
            expected = 2.0
        elif 17 <= hour < 21:
            expected = 1.5
        else:
            expected = 0.6

        flow = max(0.0, expected + rng.gauss(0, 0.12))
        actual_leak = 0

        # Ordinary short burst at 10:05-10:08.
        if 10 * 60 + 5 <= minute < 10 * 60 + 9:
            flow += 2.0

        # Sustained abnormal flow at 02:00-02:34.
        if 2 * 60 <= minute < 2 * 60 + 35:
            flow = 3.8 + rng.gauss(0, 0.08)
            actual_leak = 1

        # Another event at 14:00-14:24.
        if 14 * 60 <= minute < 14 * 60 + 25:
            flow = 2.5 + rng.gauss(0, 0.08)
            actual_leak = 1

        rows.append({
            "timestamp": timestamp.isoformat(sep=" "),
            "flow_lpm": round(flow, 3),
            "actual_leak": actual_leak,
        })

    return rows


def save_csv(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)


def ensure_data():
    """Create the demo and test CSVs if they do not exist.

    Returns (demo_rows, test_rows) so callers can reuse the data.
    """
    DEMO_PATH = DATA_DIR / "demo_readings.csv"
    TEST_PATH = DATA_DIR / "test_readings.csv"

    demo_rows = generate_readings(42)
    test_rows = generate_readings(123)

    if not DEMO_PATH.exists():
        save_csv(DEMO_PATH, demo_rows)

    if not TEST_PATH.exists():
        save_csv(TEST_PATH, test_rows)

    return demo_rows, test_rows


def main():
    save_csv(DATA_DIR / "demo_readings.csv", generate_readings(42))
    save_csv(DATA_DIR / "test_readings.csv", generate_readings(123))

    print("Generated 1,440 demo readings.")
    print("Generated 1,440 test readings.")


if __name__ == "__main__":
    main()
