# DeepFishy

An AI-powered financial research platform that autonomously researches a topic — company, industry, or macro theme — using web search, a vector knowledge base, and live financial data, then produces a structured report. Includes a chat interface for conversational Q&A backed by the same knowledge infrastructure.

## Architecture

```
DeepFishy/
├── deepfishy/          # Main Python package
│   ├── app/            # FastAPI routes, schemas, Celery workers
│   ├── features/       # Reports, chat, benchmark, ingestion, knowledge graph
│   ├── infra/          # Settings, DB, LLM factories, MinIO, Milvus, Neo4j adapters
│   └── shared/         # Logging, PDF helpers, agent utilities
├── engine/             # LangGraph orchestrators (builder, writer, synthesizer, classifier)
├── ingestion/          # Document ingestion pipeline (crawlers, chunking, parsers)
├── embedding/          # Embedding adapters (OpenAI, Google)
├── graph_rag/          # Graphiti-based knowledge graph service
├── db/                 # SQLAlchemy models
├── alembic/            # Database migrations
├── benchmark/          # Evaluation dataset, golden reports, results
├── frontend/           # Next.js web UI
├── docker/             # Docker Compose, Dockerfiles, .env.example
├── configs/            # config.yaml — LLM/VLM/embedding model registry
└── templates/          # Report outline templates (company, industry)
```

## Tech Stack

**Backend** — Python 3.11, FastAPI, LangGraph, LangChain, Graphiti, Celery + Redis, PostgreSQL, Milvus, MinIO, Neo4j, vnstock, Tavily, uv

**Frontend** — Next.js 16 (App Router), React 19, TypeScript, Tailwind CSS v4, shadcn/ui

## Features

**Report generation**
- Two-phase pipeline: `build` (research) → `write` (draft)
- `BuilderOrchestrator`: parses a report template into sections, plans sub-queries, runs parallel researcher agents (web + local knowledge base + finance data), critiques coverage, fills gaps, rewrites each section with evidence
- `WriterOrchestrator`: synthesizes the outline into a full markdown report with citations
- `ClassifierOrchestrator`: classifies the topic to select the right template (company vs. industry)
- Output: `outline.md`, `final.md`, `final.pdf`, `section_evidence_map.json`
- SSE streaming of progress events to the frontend

**Chat / Q&A** — Conversational interface with session persistence, backed by RAG over the knowledge base

**Knowledge graph** — Graphiti-based temporal knowledge graph on Neo4j; facts extracted during research are committed to the graph and queried in subsequent runs

**Document ingestion** — Scrapy crawlers, PDF parsing (MinerU, Marker), chunking + embedding pipeline into Milvus, async via Celery

**Benchmark / evaluation** — Dataset-driven report generation with LLM-as-judge scoring against golden reports

**Multi-model support** — Configurable LLM/VLM/embedding models via `configs/config.yaml`; supports OpenAI, Google AI Studio, Vertex AI, and OpenAI-compatible endpoints

## Getting Started

### Prerequisites

- Python 3.11.12+
- Docker + Docker Compose
- [uv](https://docs.astral.sh/uv/)
- Node.js 20+

### 1. Infrastructure

```bash
cd docker
cp .env.example .env   # fill in API keys and credentials
docker compose up -d
```

Services started:

| Service | Port |
|---|---|
| PostgreSQL | 1212 |
| Redis | 1213 |
| FastAPI server | 1214 |
| MinIO API | 1215 |
| MinIO Console | 1216 |
| etcd | 1217 |
| Milvus | 1218 / 1219 |
| Milvus Web UI (Attu) | 1220 |
| Neo4j Bolt | 1221 |
| Neo4j Browser | 1222 |

### 2. Backend (local dev)

```bash
uv sync
uv run alembic upgrade head
uv run uvicorn deepfishy.app.api.main:app --host 0.0.0.0 --port 8000 --reload
```

### 3. Frontend

```bash
cd frontend
npm install
npm run dev      # development with Turbopack
```

### 4. Celery workers (optional, for ingestion)

```bash
celery -A deepfishy.app.workers.celery_app:celery_app worker \
  --loglevel=info --concurrency=2 -Q crawler,ingestion,celery
```

## Environment Variables

Copy `docker/.env.example` to `docker/.env` and fill in the values.

| Variable | Description |
|---|---|
| `OPENAI_API_KEY` | OpenAI API key |
| `GOOGLE_API_KEY` | Google AI Studio API key |
| `TAVILY_API_KEY` | Tavily web search API key |
| `DATABASE_URL` | PostgreSQL connection string |
| `CELERY_BROKER_URL` | Redis URL for Celery broker |
| `CELERY_RESULT_BACKEND` | Redis URL for Celery results |
| `MILVUS_HOST` / `MILVUS_PORT` | Milvus vector DB connection |
| `MILVUS_COLLECTION_NAME` | Collection name for embeddings |
| `MILVUS_EMBEDDING_DIM` | Embedding dimension (1536 for `text-embedding-3-small`) |
| `MINIO_URL` / `MINIO_ACCESS_KEY` / `MINIO_SECRET_KEY` | Object storage |
| `NEO4J_URI` / `NEO4J_USER` / `NEO4J_PASSWORD` | Graph DB |
| `GOOGLE_CLOUD_PROJECT` / `GOOGLE_CLOUD_LOCATION` | Vertex AI config |
| `GOOGLE_APPLICATION_CREDENTIALS_FILE` | Path to GCP service account JSON |
| `RESPONSE_MODEL` | Default LLM model name |
| `LOG_LEVEL` / `NUM_WORKERS` | Logging and concurrency tuning |

## Common Entry Points

```python
from deepfishy.app.api.main import app                                              # FastAPI app
from deepfishy.app.workers.celery_app import celery_app                             # Celery app
from deepfishy.features.reports.application.generate_report import run_engine       # Single report
from deepfishy.features.reports.application.generate_dataset_reports import run_dataset_generation  # Dataset
from deepfishy.features.benchmark.evaluator import run_dataset_benchmark            # Evaluation
```

## Benchmark

Generate reports for the full dataset and evaluate in one command:

```bash
uv run python -m deepfishy.features.benchmark.run_dataset_and_evaluate \
  --dataset benchmark/dataset/dataset.csv
```

To skip generation and re-run evaluation only:

```bash
uv run python -m deepfishy.features.benchmark.run_dataset_and_evaluate \
  --dataset benchmark/dataset/dataset.csv \
  --skip_generation \
  --report_dir benchmark/generated_reports/deepfishy
```
