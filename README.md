# AQUASENTINEL

A lightweight, zero-dependency prototype for detecting sustained
abnormal water flow and estimating excess water.

## Dependencies

Python 3.10+ standard library only. Nothing to install — there is no
Streamlit, Pandas, NumPy, or Plotly anywhere in this project (see
`requirements.md`).

## Project structure

    aquasentinel/
    ├── cli.py             command-line dashboard
    ├── simulator.py       synthetic data generator
    ├── detector.py        detection engine
    ├── evaluate.py        precision / recall / F1
    ├── stress_test.py     performance and robustness test
    ├── test_detector.py   unit tests (unittest)
    ├── requirements.md    requirements document
    ├── performance.md     measured performance report
    ├── README.md          this file
    └── data/
        ├── demo_readings.csv    generated
        └── test_readings.csv    generated (labelled)

## Detection rule

An alert is raised when flow exceeds the effective baseline
(offset 0.8 L/min by default) for at least 10 consecutive one-minute
readings. With time-aware mode (the default in `cli.py`), the baseline
follows a per-hour usage schedule, so normal morning and evening use
does not trigger alerts. Excess water is estimated as
Σ max(0, flow − baseline) over the alert duration.

## Usage

Generate sample data (writes `data/*.csv`):

    python3 simulator.py

Run the unit tests:

    python3 -m unittest -v

Analyze the demo data:

    python3 cli.py analyze

Analyze a specific CSV, tune settings, and export results:

    python3 cli.py analyze --input data/test_readings.csv \
        --duration 15 --offset 1.0 --overnight-only \
        --export processed.csv

Evaluate precision / recall / F1 on labelled data:

    python3 cli.py evaluate --input data/test_readings.csv

Run the stress and robustness test:

    python3 stress_test.py 30        # 30 days = 43,200 readings

## CSV format

Required columns:

- `timestamp` — ISO format, regular one-minute sampling
- `flow_lpm` — litres per minute, non-negative

Optional evaluation column:

- `actual_leak` — synthetic label (`1` = generated event)

## Behavior guarantees (tested)

- Short bursts below the duration setting never alert.
- Flat streams and pure noise produce zero alerts.
- Negative flows, malformed rows, missing columns, empty input, and
  gaps over 90 seconds are rejected with clear errors.
- Duplicate timestamps are deduplicated (last reading wins).
- Alerts are only reported after the required consecutive readings.

## Limitations

- Default readings are synthetic; synthetic metrics do not establish
  real-world accuracy.
- Alerts indicate sustained abnormal flow, not confirmed physical
  leaks. Legitimate long use of water can also produce an alert.
- Thresholds and baselines are prototype settings and require on-site
  calibration.
- The detector assumes one-minute sampling; other intervals need
  adaptation.
- Leak location is not identified.

## Future work

- Collect and label real readings; calibrate baselines per site.
- Evaluate false positives and missed events on real data.
- Integrate a compatible flow sensor after verifying its measurement
  resolution and low-flow capability.
