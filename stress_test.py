"""AQUASENTINEL stress and robustness test.

Generates multi-day datasets (outside the project folder), runs the
detection engine, and measures throughput, memory, episode grouping
correctness, and behavior under adversarial input.

Standard library only.

Usage:
    python3 stress_test.py [days]   (default 30 days = 43,200 rows)
"""

import gc
import io
import random
import sys
import tempfile
import time
import tracemalloc
from datetime import datetime, timedelta
from pathlib import Path

from detector import detect_leaks, summarize_alerts, validate_readings
from evaluate import binary_metrics
from simulator import generate_readings, save_csv, FIELDNAMES


def build_multi_day(days, seed):
    """Concatenate single-day readings across many days."""
    rows = []
    offset = timedelta(days=0)

    for day in range(days):
        day_rows = generate_readings(seed=seed + day)
        for row in day_rows:
            shifted = datetime.fromisoformat(row["timestamp"]) + offset
            row = dict(row)
            row["timestamp"] = shifted.isoformat(sep=" ")
            rows.append(row)

        offset += timedelta(days=1)

    return rows


def timed_run(label, rows, **kwargs):
    tracemalloc.start()
    start = time.perf_counter()
    result = detect_leaks(rows, **kwargs)
    elapsed = time.perf_counter() - start
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    rate = len(rows) / elapsed if elapsed else 0
    print(f"{label}")
    print(
        f"  rows {len(rows):,} | time {elapsed:.3f} s | "
        f"{rate:,.0f} rows/s | peak memory {peak / 1_048_576:.1f} MB"
    )
    return result


def check_invariants(rows, result, label):
    errors = []

    def report(condition, message):
        if condition:
            errors.append(message)

    report(len(result) != len(rows), "row count mismatch")
    report(
        any(row["flow_lpm"] < 0 for row in result),
        "negative flow survived validation",
    )
    report(
        any(
            row["alert"] != (row["above_threshold"] and row["run_length"] >= 10)
            for row in result
        ),
        "alert flag inconsistent with run length",
    )
    report(
        any(
            row["run_length"] < 0 for row in result
        ),
        "negative run length",
    )

    episodes = summarize_alerts(result)
    for episode in episodes:
        span = (
            episode["end"] - episode["start"]
        )
        expected_minutes = span.total_seconds() // 60 + 1
        report(
            episode["duration_minutes"] != expected_minutes,
            "episode duration does not match time span",
        )
        report(
            episode["estimated_excess_litres"] <= 0,
            "episode with non-positive excess estimate",
        )

    if errors:
        print(f"  FAIL {label}: {errors}")
    else:
        print(f"  invariants OK ({len(episodes)} episodes)")

    return not errors


def main():
    days = int(sys.argv[1]) if len(sys.argv) > 1 else 30
    passed_all = True

    print("=" * 64)
    print("AQUASENTINEL stress and robustness test")
    print(f"Python {sys.version.split()[0]} | standard library only")
    print("=" * 64)

    # 1. Multi-day throughput ------------------------------------------
    print()
    print(f"1. Multi-day throughput ({days} consecutive days)")
    print("-" * 58)

    gc.collect()
    big_rows = build_multi_day(days, seed=1000)

    gc.collect()
    result = timed_run("run A: full detect_leaks", big_rows)
    passed_all &= check_invariants(big_rows, result, "run A")

    gc.collect()
    result = timed_run("run B: second pass (warm cache)", big_rows)
    passed_all &= check_invariants(big_rows, result, "run B")

    # 2. Overnight-restricted run --------------------------------------
    gc.collect()
    result = timed_run(
        "run C: overnight-only mode (full dataset)",
        big_rows,
        overnight_only=True,
    )
    passed_all &= check_invariants(big_rows, result, "run C")

    # 2. Ground-truth accuracy on multi-day data -----------------------
    print()
    print("2. Accuracy on the multi-day dataset")
    print("-" * 58)
    metrics = binary_metrics(
        [row["actual_leak"] for row in big_rows],
        [row["alert"] for row in detect_leaks(
            big_rows,
            threshold_offset_lpm=0.8,
            sustained_minutes=10,
            overnight_only=False,
            time_aware_baseline=True,
        )],
    )
    print(f"  {metrics}")
    passed_all &= metrics["FP"] == 0

    # 3. CSV round trip ------------------------------------------------
    print()
    print("3. CSV write and re-read")
    print("-" * 58)
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "stress_readings.csv"
        start_time = time.perf_counter()
        save_csv(path, big_rows)
        write_seconds = time.perf_counter() - start_time

        start_time = time.perf_counter()
        with path.open(newline="", encoding="utf-8") as file:
            reloaded = list(__import__("csv").DictReader(file))
        read_seconds = time.perf_counter() - start_time

        file_mb = path.stat().st_size / 1_048_576
        print(
            f"  wrote {len(big_rows):,} rows in {write_seconds:.2f} s, "
            f"re-read in {read_seconds:.2f} s, size {file_mb:.1f} MB"
        )
        passed_all &= len(reloaded) == len(big_rows)

    # 4. Edge cases and adversarial input ------------------------------
    print()
    print("4. Edge cases and adversarial input")
    print("-" * 58)

    # Duplicated timestamps.
    start = datetime(2026, 10, 25, 2, 0)
    duplicated = [
        {"timestamp": start.isoformat(sep=" "), "flow_lpm": 3.8}
    ] * 12
    try:
        result = detect_leaks(duplicated)
        ok = len(result) == 1
    except ValueError:
        ok = False
    print(f"  12 identical readings -> deduplicated: {ok}")
    passed_all &= ok

    # Empty input.
    try:
        detect_leaks([])
        ok = False
    except ValueError:
        ok = True
    print(f"  empty input rejected: {ok}")
    passed_all &= ok

    # Malformed values.
    bad_rows = [
        {"timestamp": "not-a-time", "flow_lpm": "abc"},
        {
            "timestamp": (start + timedelta(minutes=1)).isoformat(sep=" "),
            "flow_lpm": 0.2,
        },
    ]
    try:
        detect_leaks(bad_rows)
        ok = False
    except ValueError:
        ok = True
    print(f"  malformed row rejected: {ok}")
    passed_all &= ok

    # Gap in the data.
    gapped = [
        {
            "timestamp": (start + timedelta(minutes=i)).isoformat(sep=" "),
            "flow_lpm": 0.2,
        }
        for i in range(5)
    ] + [
        {
            "timestamp": (start + timedelta(hours=5)).isoformat(sep=" "),
            "flow_lpm": 0.2,
        }
    ]
    try:
        detect_leaks(gapped)
        ok = False
    except ValueError:
        ok = True
    print(f"  large gap rejected: {ok}")
    passed_all &= ok

    # Flat stream and pure noise never alert.
    rng = random.Random(7)
    flat = [
        {
            "timestamp": (start + timedelta(minutes=i)).isoformat(sep=" "),
            "flow_lpm": 0.2,
        }
        for i in range(1440)
    ]
    noisy = [
        {
            "timestamp": (start + timedelta(minutes=i)).isoformat(sep=" "),
            "flow_lpm": round(max(0.0, rng.gauss(0.6, 0.15)), 3),
        }
        for i in range(1440)
    ]
    steady_result = detect_leaks(flat, time_aware_baseline=True)
    noisy_result = detect_leaks(noisy, time_aware_baseline=True)
    ok = not any(row["alert"] for row in steady_result)
    ok &= not any(row["alert"] for row in noisy_result)
    print(f"  flat and noisy streams produce zero alerts: {ok}")
    passed_all &= ok

    # Contract: validation is idempotent for consistent data.
    cleaned = validate_readings(generate_readings(99))
    ok = validate_readings(cleaned) == cleaned
    print(f"  validation idempotent on clean data: {ok}")
    passed_all &= isinstance(cleaned, list) and ok

    print()
    print("=" * 64)
    print("STRESS TEST " + ("PASSED" if passed_all else "FAILED"))
    print("=" * 64)
    return 0 if passed_all else 1


if __name__ == "__main__":
    sys.exit(main())
