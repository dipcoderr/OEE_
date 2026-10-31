# OEE Workflow Synthetic Data Generator

This project creates a synthetic manufacturing dataset for calculating availability, performance, quality, and overall equipment effectiveness (OEE) from machine-state events, production counts, and quality outcomes.

## Project goals

- Generate deterministic master data and transaction records.
- Preserve full event history without overwriting prior state.
- Produce traceability via referenced IDs and annotated anomaly labels.
- Keep a separate ground-truth artifact for known exceptions and expected decisions.
- Validate the generated data with integrity and reconciliation checks.
- Demonstrate fixed-seed reproducibility across repeated runs.

## Generator command

```bash
cd /Users/himanshu/workspace/oee_workflow
python3 generator.py --seed 20261022 --scale 1.0 --output-dir data --repro-check
```

The schema and field definitions are also captured in [data_dictionary.md](data_dictionary.md).

## Dataset contents

This generator creates the following tables:

- Plant
- Line
- Machine
- Shift
- Product
- ProductionOrder
- StateEvent
- ProductionCount
- QualityInspection
- DowntimeReason
- OEEAggregate

## Baseline volume

The default full dataset is built around the requested baseline:

- 5 lines
- 30 machines
- 20 products
- 90 days of shifts
- 100,000 state events
- 500,000 count/inspection records

The generator uses `scale` to parameterize the volume while keeping the same logic:

- `scale=0.01` for a starter dataset
- `scale=1.0` for the full synthetic baseline

## Known edge cases

The dataset intentionally includes labelled exceptions without silently invalidating unrelated rows:

- overlapping machine states
- count decreases without a correction event
- scrap exceeds total sample quantity
- wrong ideal cycle time
- downtime overlaps planned break

These are stored in the separate ground truth artifact and are not mixed into the main feature data. The exported files are written to the `csv` and `json` folders, with `ground_truth.csv` and `ground_truth.json` kept separate from the model inputs.

## Output structure

```text
data/
  csv/
    Plant.csv
    Line.csv
    Machine.csv
    Shift.csv
    Product.csv
    ProductionOrder.csv
    StateEvent.csv
    ProductionCount.csv
    QualityInspection.csv
    DowntimeReason.csv
    OEEAggregate.csv
  json/
    dataset.json
    ground_truth.json
  seed.sql
  source_manifest.json
  validation_summary.json
  reproducibility_summary.json
```

## Validation rules

The script checks:

- primary-key uniqueness
- foreign-key integrity
- allowed enumerations
- date ordering and shift timing
- derived OEE arithmetic
- lifecycle consistency and anomaly handling

## Reproducibility

The generator keeps a fixed seed (`20261022`) and writes a reproducibility summary after a second identical generation pass. Row counts and SHA256 checksums are compared to confirm deterministic output.

## Data provenance note

This project uses synthetic manufacturing data only. The intended use is for workflow demonstration, data-quality checks, and reproducible analytical experiments.
