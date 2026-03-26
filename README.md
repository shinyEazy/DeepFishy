# DeepFishy

## Benchmark

Generate reports for the whole dataset and evaluate them in one command:

```bash
.venv/bin/python benchmark/run_dataset_and_evaluate.py \
  --dataset benchmark/dataset/dataset.csv
```

This will:

1. Run dataset generation with `engine/main.py`, writing PDFs to `benchmark/generated_reports/deepfishy`.
2. Run `benchmark/evaluate.py` against that directory.

If the reports already exist and you only want to re-run evaluation:

```bash
.venv/bin/python benchmark/run_dataset_and_evaluate.py \
  --dataset benchmark/dataset/dataset.csv \
  --skip_generation \
  --report_dir benchmark/generated_reports/deepfishy
```
