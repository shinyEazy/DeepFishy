# DeepFishy

DeepFishy is a backend for financial research workflows, benchmark evaluation, chat/session APIs, crawling, embedding, and knowledge-search pipelines.

## Canonical Structure

The repository now treats `deepfishy/` as the authoritative Python package root.

Primary ownership boundaries:

- `deepfishy.app`
  API factory, API routes, API schemas, Celery bootstrap, and worker tasks.
- `deepfishy.features`
  Report generation, benchmark evaluation, chat behavior, ingestion helpers, and knowledge-search services.
- `deepfishy.infra`
  Settings, model registry, paths, DB/session setup, LLM factories, MinIO, Milvus, and Neo4j adapters.
- `deepfishy.shared`
  Logging, crawler constants, shared PDF helpers, and shared agent-loading utilities.

Legacy top-level directories such as `api/`, `worker/`, `benchmark/`, `services/`, `core/`, and much of `utils/` are now primarily compatibility wrappers. New code should prefer package imports from `deepfishy.*`.

## Common Entry Points

FastAPI application:

```python
from deepfishy.app.api.main import app
```

Celery application:

```python
from deepfishy.app.workers.celery_app import celery_app
```

Single report generation:

```python
from deepfishy.features.reports.application.generate_report import run_engine
```

Dataset report generation:

```python
from deepfishy.features.reports.application.generate_dataset_reports import run_dataset_generation
```

Benchmark evaluation:

```python
from deepfishy.features.benchmark.evaluator import run_dataset_benchmark
```

## Benchmark

Generate reports for the whole dataset and evaluate them in one command:

```bash
.venv/bin/python -m deepfishy.features.benchmark.run_dataset_and_evaluate \
  --dataset benchmark/dataset/dataset.csv
```

This will:

1. Run dataset generation through `deepfishy.features.reports.application.generate_dataset_reports`.
2. Run benchmark evaluation through `deepfishy.features.benchmark.evaluator`.

If the reports already exist and you only want to re-run evaluation:

```bash
.venv/bin/python -m deepfishy.features.benchmark.run_dataset_and_evaluate \
  --dataset benchmark/dataset/dataset.csv \
  --skip_generation \
  --report_dir benchmark/generated_reports/deepfishy
```

## Refactor Status

The structural refactor is complete enough that `deepfishy/` is now the source of truth for active runtime code.

Remaining legacy modules are intentionally left in place as compatibility layers so older imports and scripts continue to work while callers migrate gradually.
