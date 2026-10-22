"""AQUASENTINEL detection engine.

Validates inputs, detects sustained abnormal flow, estimates excess
water, and groups consecutive alert readings into episodes.

Standard library only. No external dependencies.

False-reading safeguards
------------------------
- Input validation: missing columns, invalid values, negative flow,
  large sampling gaps, and duplicate timestamps are handled.
- Time-of-day aware baseline: normal high-use periods (mornings,
  evenings) are compared against their own baseline instead of the
  overnight baseline, so ordinary use does not trigger alerts.
- Relative threshold: the alert threshold is an offset above the
  effective baseline for each period.
- Duration gate: only sustained runs of consecutive readings qualify.
"""

from datetime import datetime, timedelta

REQUIRED_COLUMNS = {"timestamp", "flow_lpm"}

# Expected baseline (L/min) for each hour of the day, derived from the
# simulator's usage schedule. Used when time-aware detection is enabled.
# These are prototype settings, not validated plumbing standards.
DEFAULT_BASELINE_SCHEDULE = {
    0: 0.2, 1: 0.2, 2: 0.2, 3: 0.2, 4: 0.2,
    5: 0.6,
    6: 2.0, 7: 2.0, 8: 2.0,
    9: 0.6, 10: 0.6, 11: 0.6, 12: 0.6, 13: 0.6, 14: 0.6,
    15: 0.6, 16: 0.6,
    17: 1.5, 18: 1.5, 19: 1.5, 20: 1.5,
    21: 0.6, 22: 0.6, 23: 0.6,
}


def parse_timestamp(value):
    return datetime.fromisoformat(value)


def validate_readings(rows, max_gap_seconds=90):
    """Clean and validate readings; raises ValueError on bad input.

    max_gap_seconds allows callers that use non-default sampling to
    relax the maximum gap between consecutive readings. The default
    of 90 seconds assumes one-minute sampling.
    """
    if not rows:
        raise ValueError("No readings were supplied.")

    cleaned = []
    seen = {}

    for index, row in enumerate(rows):
        if not REQUIRED_COLUMNS.issubset(row):
            raise ValueError(
                f"Row {index + 1} is missing required columns: "
                "timestamp, flow_lpm."
            )

        try:
            timestamp = parse_timestamp(str(row["timestamp"]))
            flow = float(row["flow_lpm"])
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"Row {index + 1} has an invalid timestamp or flow value."
            ) from exc

        if flow < 0:
            raise ValueError(
                f"Row {index + 1}: flow readings cannot be negative."
            )

        item = dict(row)
        item["timestamp"] = timestamp
        item["flow_lpm"] = flow

        # Keep the last reading for duplicate timestamps.
        seen[timestamp] = item

    for timestamp in sorted(seen):
        cleaned.append(seen[timestamp])

    if not cleaned:
        raise ValueError("No valid readings remain.")

    # This detector expects regular sampling (one reading per minute
    # by default); reject larger gaps.
    max_gap = timedelta(seconds=max(1, max_gap_seconds))

    for previous, current in zip(cleaned, cleaned[1:]):
        gap = current["timestamp"] - previous["timestamp"]

        if gap > max_gap:
            raise ValueError(
                "Readings have a gap greater than "
                f"{max(1, max_gap_seconds)} seconds. "
                "Use regular one-minute readings."
            )

    return cleaned


def effective_baseline(hour, baseline_lpm, schedule=None):
    """Return the baseline in force for a given hour."""
    if schedule is None:
        return baseline_lpm
    return schedule.get(hour, baseline_lpm)


def detect_leaks(
    rows,
    baseline_lpm=0.2,
    threshold_offset_lpm=0.8,
    sustained_minutes=10,
    overnight_only=False,
    time_aware_baseline=False,
    schedule=None,
):
    """Detect sustained abnormal flow.

    baseline_lpm          absolute baseline used when
                          time_aware_baseline is False.
    threshold_offset_lpm  a reading must exceed
                          effective baseline + this offset.
    sustained_minutes     consecutive readings required for an alert.
    overnight_only        restrict detection to 00:00-04:59.
    time_aware_baseline   use the DEFAULT_BASELINE_SCHEDULE by hour.
    schedule              custom {hour: baseline} mapping; enables
                          time-aware mode automatically.
    """
    if baseline_lpm < 0:
        raise ValueError("Baseline cannot be negative.")

    if threshold_offset_lpm < 0:
        raise ValueError("Threshold offset cannot be negative.")

    if sustained_minutes < 1:
        raise ValueError("Duration must be at least one minute.")

    if schedule is not None:
        time_aware = True
        schedule = {
            int(hour): max(0.0, float(value))
            for hour, value in schedule.items()
        }
    else:
        time_aware = time_aware_baseline
        schedule = DEFAULT_BASELINE_SCHEDULE

    readings = validate_readings(rows)
    result = []
    run_length = 0

    for item in readings:
        timestamp = item["timestamp"]
        flow = item["flow_lpm"]

        eligible_time = (
            not overnight_only
            or 0 <= timestamp.hour < 5
        )

        baseline = effective_baseline(timestamp.hour, baseline_lpm)
        if time_aware:
            baseline = schedule.get(timestamp.hour, baseline_lpm)

        threshold = baseline + threshold_offset_lpm
        above = eligible_time and flow > threshold

        if above:
            run_length += 1
        else:
            run_length = 0

        alert = above and run_length >= sustained_minutes
        excess_lpm = max(0.0, flow - baseline)

        if alert:
            reason = "Sustained abnormal flow: inspect for possible leak"
        else:
            reason = (
                "Flow exceeds threshold but has not persisted long enough"
                if above
                else "Flow is within the configured threshold"
            )

        output = dict(item)
        output.update({
            "baseline_lpm": round(baseline, 3),
            "threshold_lpm": round(threshold, 3),
            "above_threshold": above,
            "run_length": run_length,
            "alert": alert,
            "excess_lpm": round(excess_lpm, 3),
            "estimated_excess_litres": (
                round(excess_lpm, 3) if alert else 0.0
            ),
            "reason": reason,
        })

        result.append(output)

    return result


def summarize_alerts(rows, gap_minutes=1):
    """Group adjacent alert rows into episodes."""
    episodes = []
    current = []

    def finish_episode():
        if not current:
            return

        episodes.append({
            "start": current[0]["timestamp"],
            "end": current[-1]["timestamp"],
            "duration_minutes": len(current),
            "peak_flow_lpm": round(
                max(row["flow_lpm"] for row in current), 2
            ),
            "estimated_excess_litres": round(
                sum(row["estimated_excess_litres"] for row in current),
                2,
            ),
        })

    max_gap = timedelta(minutes=gap_minutes)

    for row in rows:
        if row["alert"]:
            if current:
                gap = row["timestamp"] - current[-1]["timestamp"]

                if gap > max_gap:
                    finish_episode()
                    current.clear()

            current.append(row)
        elif current:
            finish_episode()
            current.clear()

    finish_episode()
    return episodes


def print_report(result, episodes):
    """Human-readable console report."""
    alert_rows = [row for row in result if row["alert"]]

    print()
    print("=" * 62)
    print("AQUASENTINEL - analysis report")
    print("=" * 62)
    print(f"Readings analyzed  : {len(result):,}")
    print(f"Alert readings     : {len(alert_rows):,}")
    print(f"Alert episodes     : {len(episodes)}")
    print(
        f"Estimated excess   : "
        f"{sum(row['estimated_excess_litres'] for row in result):,.1f} L"
    )

    for episode in episodes:
        print()
        print(
            f"  Episode {episode['start']} -> {episode['end']}"
        )
        print(
            f"    duration {episode['duration_minutes']} min | "
            f"peak {episode['peak_flow_lpm']:.2f} L/min | "
            f"excess ~{episode['estimated_excess_litres']:.1f} L"
        )

    if not episodes:
        print()
        print("No sustained abnormal-flow episode was detected.")
        print("This does not guarantee that no leak exists.")

    print()
    print("Alerts indicate abnormal flow, not confirmed physical leaks.")
    print("=" * 62)
