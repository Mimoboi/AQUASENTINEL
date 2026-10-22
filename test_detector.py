"""AQUASENTINEL detector tests (unittest, no external dependency)."""

import unittest
from datetime import datetime, timedelta

from detector import detect_leaks, DEFAULT_BASELINE_SCHEDULE, summarize_alerts


def make_data(flows, start=datetime(2026, 10, 25, 2, 0)):
    return [
        {
            "timestamp": (start + timedelta(minutes=i)).isoformat(sep=" "),
            "flow_lpm": flow,
        }
        for i, flow in enumerate(flows)
    ]


class DetectorTests(unittest.TestCase):
    def test_short_burst_does_not_alert(self):
        rows = make_data([0.2] * 5 + [2.0] * 4 + [0.2] * 5)
        result = detect_leaks(rows)

        self.assertFalse(any(row["alert"] for row in result))

    def test_sustained_flow_alerts(self):
        rows = make_data([0.2] * 3 + [3.8] * 12)
        result = detect_leaks(rows)

        self.assertEqual(
            sum(row["alert"] for row in result),
            3,
        )

    def test_negative_flow_is_rejected(self):
        rows = make_data([0.2, -1.0, 0.3])

        with self.assertRaises(ValueError):
            detect_leaks(rows)

    def test_threshold_offset_cannot_be_negative(self):
        rows = make_data([0.2, 0.3])

        with self.assertRaises(ValueError):
            detect_leaks(rows, threshold_offset_lpm=-1.0)

    def test_episode_summary(self):
        rows = make_data([0.2] * 2 + [3.8] * 12)
        result = detect_leaks(rows)
        episodes = summarize_alerts(result)

        self.assertEqual(len(episodes), 1)
        self.assertGreater(
            episodes[0]["estimated_excess_litres"],
            0,
        )

    def test_two_separate_episodes(self):
        rows = make_data(
            [0.2] * 12 + [3.8] * 12 + [0.2] * 5 + [3.5] * 12
        )
        result = detect_leaks(rows)
        episodes = summarize_alerts(result)

        self.assertEqual(len(episodes), 2)
        self.assertTrue(all(
            episode["estimated_excess_litres"] > 0
            for episode in episodes
        ))

    def test_time_aware_baseline_ignores_normal_daytime_use(self):
        # 10:00-10:30 with baseline 0.6 and flows up to 1.2};
        # a fixed 0.2 baseline would falsely classify this.
        flows = [0.8] * 30
        rows = make_data(flows, start=datetime(2026, 10, 26, 10, 0))
        result = detect_leaks(rows, time_aware_baseline=True)

        self.assertFalse(any(row["alert"] for row in result))

    def test_time_aware_baseline_detects_daytime_event(self):
        # 14:00-15:00 at 2.5 L/min against a 0.6 baseline.
        flows = [2.5] * 30
        rows = make_data(flows, start=datetime(2026, 10, 26, 14, 0))
        result = detect_leaks(rows, time_aware_baseline=True)

        self.assertEqual(sum(row["alert"] for row in result), 21)

    def test_custom_schedule_overrides_default(self):
        schedule = dict(DEFAULT_BASELINE_SCHEDULE)
        schedule[2] = 3.0  # high baseline overnight; event hidden
        rows = make_data([3.2] * 12)
        result = detect_leaks(rows, schedule=schedule)

        self.assertTrue(all(row["baseline_lpm"] == 3.0 for row in result))
        self.assertFalse(any(row["alert"] for row in result))

    def test_missing_column_is_rejected(self):
        rows = [{"timestamp": "2026-10-25 02:00:00"}]

        with self.assertRaises(ValueError):
            detect_leaks(rows)

    def test_gaps_are_rejected(self):
        start = datetime(2026, 10, 25, 2, 0)
        rows = [
            {"timestamp": start.isoformat(sep=" "), "flow_lpm": 0.2},
            {
                "timestamp": (start + timedelta(minutes=20)).isoformat(sep=" "),
                "flow_lpm": 0.3,
            },
        ]

        with self.assertRaises(ValueError):
            detect_leaks(rows)

    def test_duplicate_timestamps_keep_last_reading(self):
        start = datetime(2026, 10, 25, 2, 0)
        rows = [
            {"timestamp": start.isoformat(sep=" "), "flow_lpm": 0.2},
            {"timestamp": start.isoformat(sep=" "), "flow_lpm": 0.6},
            {
                "timestamp": (start + timedelta(minutes=1)).isoformat(sep=" "),
                "flow_lpm": 0.4,
            },
        ]
        result = detect_leaks(rows)

        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["flow_lpm"], 0.6)

    def test_overnight_only_ignores_daytime(self):
        flows = [3.8] * 12
        rows = make_data(flows, start=datetime(2026, 10, 26, 14, 0))
        result = detect_leaks(rows, overnight_only=True)

        self.assertFalse(any(row["alert"] for row in result))


if __name__ == "__main__":
    unittest.main()
