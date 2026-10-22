# AQUASENTINEL — Requirements

## Python

Python 3.10 or newer (standard library only). The project was
finalized and tested with Python 3.14.

## External dependencies

None. The earlier Streamlit dashboard was replaced by `cli.py`,
so there is nothing to install.

## Runtime components

| Module          | Source              | Purpose                          |
| --------------- | ------------------- | -------------------------------- |
| `cli.py`        | project             | command-line dashboard           |
| `simulator.py`  | project             | synthetic data generation        |
| `detector.py`   | project             | detection engine                 |
| `evaluate.py`   | project             | precision / recall / F1          |
| `stress_test.py`| project             | performance and robustness tests |
| `csv`           | standard library    | reading and writing CSVs         |
| `datetime`      | standard library    | timestamps and durations         |
| `random`        | standard library    | simulated flow noise             |
| `unittest`      | standard library    | automated tests                  |
| `timeit`/`tracemalloc` | standard library | performance measurement |

## Input data format

CSV with required columns:

- `timestamp` — ISO format, one-minute sampling
- `flow_lpm` — litres per minute, non-negative

Optional column:

- `actual_leak` — synthetic label for evaluation only

## Storage budget

The completed project occupies well under 50 MB (see
`performance.md` for measured sizes). Generated datasets stay small;
multi-day stress datasets are written outside the project folder or
deleted after testing.
