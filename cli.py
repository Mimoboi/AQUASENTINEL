"""AQUASENTINEL command-line dashboard.

Replaces the Streamlit dashboard with a standard-library-only CLI,
so the project has zero external dependencies.

Usage examples
--------------

    python3 cli.py analyze                          (demo data)
    python3 cli.py analyze --input data/test_readings.csv
    python3 cli.py analyze --duration 15 --offset 1.0 --overnight-only
    python3 cli.py analyze --export processed.csv
    python3 cli.py evaluate                         (synthetic metrics)

The tool validates settings, reports clear errors, and prints a
summary of alert episodes with estimated excess water.
"""

import argparse
import csv
import sys
from pathlib import Path

from detector import detect_leaks, print_report, summarize_alerts


def read_csv_path(path):
    with path.open(newline="", encoding="utf-8-sig") as file:
        return list(csv.DictReader(file))


def write_csv(path, rows):
    fieldnames = [
        "timestamp",
        "flow_lpm",
        "actual_leak",
        "baseline_lpm",
        "threshold_lpm",
        "above_threshold",
        "run_length",
        "alert",
        "excess_lpm",
        "estimated_excess_litres",
        "reason",
    ]
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames,
                                extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    print(f"Processed readings exported to {path} "
          f"({len(rows):,} rows).")


def display(rows, baseline, offset, duration, overnight, exported):
    source = "'demo data' or 'uploaded file'"
    try:
        result = detect_leaks(
            rows,
            baseline_lpm=baseline,
            threshold_offset_lpm=offset,
            sustained_minutes=duration,
            overnight_only=overnight,
            time_aware_baseline=True,
        )
    except (ValueError, TypeError, KeyError) as exc:
        print(f"Error: cannot process readings: {exc}")
        sys.exit(2)

    episodes = summarize_alerts(result)

    if exported:
        safe_rows = []
        for row in result:
            item = dict(row)
            if hasattr(item.get("timestamp"), "isoformat"):
                item["timestamp"] = item["timestamp"].isoformat(sep=" ")
            safe_rows.append(item)
        write_csv(exported, safe_rows)

    print(f"Settings: baseline schedule (time-aware) | "
          f"offset {offset:.2f} L/min | duration {duration} min | "
          f"overnight-only: {'yes' if overnight else 'no'}")
    print_report(result, episodes)


def main():
    parser = argparse.ArgumentParser(
        prog="AQUASENTINEL",
        description=(
            "Detect sustained abnormal water flow and estimate "
            "excess water. Reads one-minute flow CSVs with columns "
            "timestamp and flow_lpm."
        ),
    )

    sub = parser.add_subparsers(dest="command", required=True)

    # analyze ---------------------------------------------------------
    analyze = sub.add_parser(
        "analyze",
        help="analyze a readings CSV",
    )
    analyze.add_argument(
        "--input",
        default=None,
        help="CSV to analyze (default: generated demo data)",
    )
    analyze.add_argument(
        "--duration",
        type=int,
        default=10,
        help="sustained minutes required for an alert (default 10)",
    )
    analyze.add_argument(
        "--offset",
        type=float,
        default=0.8,
        help=("threshold offset above the period baseline in L/min "
              "(default 0.8)"),
    )
    analyze.add_argument(
        "--baseline",
        type=float,
        default=None,
        help=("absolute baseline in L/min; disables the time-of-day "
              "schedule when set"),
    )
    analyze.add_argument(
        "--overnight-only",
        action="store_true",
        help="restrict alerts to 00:00-04:59",
    )
    analyze.add_argument(
        "--export",
        default=None,
        help="write processed readings to this CSV path",
    )

    # evaluate --------------------------------------------------------
    evaluate = sub.add_parser(
        "evaluate",
        help="precision / recall / F1 on synthetic labelled data",
    )
    evaluate.add_argument(
        "--input",
        default="data/test_readings.csv",
        help="labelled CSV to evaluate (default: data/test_readings.csv)",
    )
    evaluate.add_argument(
        "--duration",
        type=int,
        default=10,
        help="sustained minutes required for an alert (default 10)",
    )
    evaluate.add_argument(
        "--offset",
        type=float,
        default=0.8,
        help="threshold offset above the period baseline (default 0.8)",
    )

    args = parser.parse_args()

    if args.command == "analyze":
        if args.input:
            path = Path(args.input)
            if not path.exists():
                print(f"Error: {path} not found.")
                sys.exit(2)
            rows = read_csv_path(path)
            print(f"Data source: {path}")
        else:
            from simulator import ensure_data
            rows = ensure_data()[0]
            print("Data source: generated demo data")

        if args.duration < 1:
            print("Error: duration must be at least one minute.")
            sys.exit(2)

        display(
            rows,
            args.baseline if args.baseline is not None else 0.2,
            args.offset,
            args.duration,
            args.overnight_only,
            args.export,
        )

    elif args.command == "evaluate":
        from evaluate import run_evaluation
        run_evaluation(
            Path(args.input),
            duration=args.duration,
            offset=args.offset,
        )


if __name__ == "__main__":
    main()
