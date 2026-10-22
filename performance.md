# AQUASENTINEL — Performance Report

All measurements were taken on the target device (Android/Termux,
Python 3.14.6, standard library only) on 22 October 2026, with
default settings (time-aware baseline, offset 0.8 L/min, duration
10 minutes). `python3 stress_test.py <days>` reproduces these numbers.

## 1. Throughput and memory

| Dataset                  | Rows   | Time (s) | Throughput (rows/s) | Peak memory |
| ------------------------ | ------ | -------- | ------------------- | ----------- |
| 30 days                  | 43,200 | 2.57     | ~16,800             | 32.3 MB     |
| 30 days (warm cache)     | 43,200 | 2.59     | ~16,700             | 32.3 MB     |
| 30 days overnight-only   | 43,200 | 2.49     | ~17,300             | 32.0 MB     |
| 60 days                  | 86,400 | 5.26     | ~16,400             | 64.6 MB     |
| 60 days overnight-only   | 86,400 | 5.13     | ~16,800             | 64.0 MB     |

Observations:

- Throughput is stable at roughly 16,000–17,000 readings per second
  regardless of dataset size (linear scaling, no degradation).
- Memory grows linearly with input size (~0.75 MB per day of
  one-minute readings including result copies). A full year of
  one-minute readings (525,600 rows) would stay around ~390 MB and
  could be streamed in monthly chunks if ever needed.
- Overnight-only mode is slightly faster because fewer readings are
  eligible for alerts.

## 2. Detection accuracy on synthetic ground truth

| Dataset            | TP    | FP | FN  | Precision | Recall | F1    |
| ------------------ | ----- | -- | --- | --------- | ------ | ----- |
| 1 day (1,440 rows) | 42    | 0  | 18  | 1.000     | 0.700  | 0.824 |
| 30 days (43,200)   | 1,260 | 0  | 540 | 1.000     | 0.700  | 0.824 |

- **Zero false positives** across all runs — no false readings were
  produced on synthetic or adversarial input.
- All false negatives are the first 9 minutes of each event (the
  duration gate requires 10 consecutive readings before the first
  alert), which is correct, documented behavior rather than an error.
- Results are identical for 1 day and 30 days, confirming consistent
  behavior over time.

## 3. CSV I/O

| Operation                        | Rows   | Time    | Size    |
| -------------------------------- | ------ | ------- | ------- |
| Write CSV                        | 43,200 | 0.35 s  | 1.2 MB  |
| Read CSV                         | 43,200 | 0.21 s  | 1.2 MB  |

## 4. Robustness (edge cases — all passed)

| Case                                   | Result                                  |
| -------------------------------------- | --------------------------------------- |
| 12 identical (duplicate) readings      | Deduplicated to 1 reading               |
| Empty input                            | Rejected with `ValueError`              |
| Malformed timestamp / flow             | Rejected with `ValueError`              |
| Missing required column                | Rejected with `ValueError`              |
| Negative flow                          | Rejected with `ValueError`              |
| 5-hour gap between readings            | Rejected with `ValueError`              |
| Flat stream (24 h at baseline)         | Zero alerts                             |
| Pure noise (24 h, σ = 0.15)            | Zero alerts                             |
| Validation on clean data               | Idempotent                              |
| Alert/run-length consistency           | Verified on every stress run            |
| Episode duration vs. time span         | Verified for all 240 episodes (60 days) |

## 5. Storage footprint (well under the 50 MB budget)

| Item                       | Size    |
| -------------------------- | ------- |
| Entire project folder      | ~215 KB |
| `data/demo_readings.csv`   | 44 KB   |
| `data/test_readings.csv`   | 44 KB   |
| 30-day stress CSV          | 1.2 MB (written to system temp, not stored) |
| State of copy count in folder after tests  | unchanged — stress data is temporary |

No virtual environment is shipped in the folder, and no external
packages are installed, so the project cannot exceed the 50 MB limit
through normal use.

## 6. Unit tests

`python3 -m unittest -v` — **13 tests, all pass in 0.006 s.**

## 7. Conclusion

The prototype meets the lightweight goals: zero external
dependencies, sub-250 KB footprint, ~17,000 readings/s sustained
throughput, zero false positives, and deterministic, well-defined
behavior on invalid or adversarial input.
