# DeepFishy Refactor Design

**Date:** 2026-04-14

**Goal:** Restructure the DeepFishy backend into a feature-first Python package with explicit application entrypoints and shared infrastructure adapters, so that future work happens inside clear workflow boundaries instead of being scattered across generic folders like `services/`, `utils/`, and `engine/`.

## Current Problems

The current repository has working subsystems, but its structure is fighting the way the code actually behaves:

- Runtime workflows are feature-oriented, but the filesystem is mostly organized by vague technical buckets.
- Core logic is spread across `api/`, `services/`, `utils/`, `engine/`, `benchmark/`, `worker/`, and ad hoc scripts.
- `engine/main.py` acts as a god module for report generation, dataset generation, output assembly, and agent/model bootstrap.
- Configuration is fragmented across `core/config.py`, `utils/load_config.py`, and many direct `os.getenv(...)` calls.
- Some scripts mutate `sys.path` to make imports work, which is a strong signal that package boundaries are missing.
- Entry points are mixed with business logic, so routes and scripts sometimes reach into modules that should not be part of their dependency surface.

## Design Principles

This refactor should follow these principles:

1. Organize by workflow ownership first, not by generic helper categories.
2. Keep API, worker, and CLI modules thin; they should call into application services rather than contain business logic.
3. Centralize infrastructure integrations such as LLMs, databases, object storage, vector DBs, and graph adapters under one `infra/` boundary.
4. Replace catch-all folders like `utils/` and `services/` with explicit homes based on responsibility.
5. Introduce one authoritative configuration layer and one authoritative path policy.
6. Eliminate `sys.path.insert(...)` and ad hoc project root resolution from runtime modules.
7. Make each major feature mostly editable within one subtree.

## Target Package Layout

The target Python backend should live under a real package root:

```text
deepfishy/
  app/
    api/
      factory.py
      deps.py
      routes/
      schemas/
    workers/
      celery_app.py
      tasks/
    cli/
      report.py
      benchmark.py
      devtools.py

  features/
    chat/
      service.py
      repository.py
      dto.py
    reports/
      application/
        generate_report.py
        generate_dataset_reports.py
        finalize_report.py
      orchestrators/
      prompts/
      tools/
      templates/
    benchmark/
      evaluate.py
      dataset.py
      prompts.py
      results.py
    ingestion/
      application/
      crawler/
      parsers/
      chunking/
    knowledge_graph/
      service.py
      entity_types.py

  infra/
    config/
      settings.py
      model_registry.py
      paths.py
    db/
      base.py
      session.py
      models/
    llm/
      chat_factory.py
      embedding_factory.py
    storage/
      minio.py
    vector/
      milvus.py
    graph/
      neo4j.py

  shared/
    logging.py
    constants.py
    agents.py
    serialization.py
    io/
    pdf/
    text/
```

Top-level repository layout after migration:

```text
deepfishy/        # package root
frontend/
docker/
configs/
scripts/
docs/
alembic/
pyproject.toml
README.md
```

## Dependency Rules

Allowed dependency direction:

- `deepfishy.app` may depend on `deepfishy.features`, `deepfishy.infra`, and `deepfishy.shared`.
- `deepfishy.features` may depend on `deepfishy.infra` and `deepfishy.shared`.
- `deepfishy.infra` may depend on `deepfishy.shared`.
- `deepfishy.shared` should have no local dependencies other than truly generic helpers.

Disallowed patterns:

- API routes importing script-style modules such as `engine.main`.
- Feature code importing from application entrypoints.
- New code added to `utils/` or `services/`.
- New direct `os.getenv(...)` calls outside the config layer unless there is a very narrow bootstrap reason.

## Repo-Specific File Mapping

### Entry Points

- `main.py` -> `deepfishy/app/api/factory.py`
- `celery_app.py` -> `deepfishy/app/workers/celery_app.py`
- `vertexai.py` -> `scripts/vertexai_smoke_test.py` or delete if obsolete

### API Layer

- `api/deps.py` -> `deepfishy/app/api/deps.py`
- `api/routes/*` -> `deepfishy/app/api/routes/*`
- `api/schemas/*` -> `deepfishy/app/api/schemas/*`

### Report Generation

- `engine/orchestrators/*` -> `deepfishy/features/reports/orchestrators/*`
- `engine/prompts/*` -> `deepfishy/features/reports/prompts/*`
- `engine/tools/*` -> `deepfishy/features/reports/tools/*`
- `engine/subagents/*` -> `deepfishy/features/reports/subagents/*` if still used, otherwise merge into prompts/templates
- `templates/*` -> `deepfishy/features/reports/templates/*`
- `engine/main.py` split into:
  - `deepfishy/features/reports/application/generate_report.py`
  - `deepfishy/features/reports/application/generate_dataset_reports.py`
  - `deepfishy/features/reports/application/finalize_report.py`
  - `deepfishy/app/cli/report.py`

### Benchmarking

- `benchmark/evaluate.py` -> `deepfishy/features/benchmark/evaluate.py`
- `benchmark/prompt.py` -> `deepfishy/features/benchmark/prompts.py`
- `utils/results_io.py` -> `deepfishy/features/benchmark/results.py`
- `utils/response_parser.py` -> `deepfishy/features/benchmark/results.py`
- `utils/report_discovery.py` -> `deepfishy/features/benchmark/results.py`
- `benchmark/run_dataset_and_evaluate.py` -> `deepfishy/app/cli/benchmark.py`
- `benchmark/convert_folder_to_pdf.py` -> `scripts/convert_benchmark_folder_to_pdf.py` if still needed
- `benchmark/dataset/*` stays as data, not package code

### Chat

- `services/chat.py` -> `deepfishy/features/chat/service.py`
- DB-specific chat reads/writes should move into `deepfishy/features/chat/repository.py`

### Ingestion

- `ingestion/*` -> `deepfishy/features/ingestion/*`
- `worker/tasks/crawler_task.py` stays task-oriented under `deepfishy/app/workers/tasks/`, but its logic should call into ingestion application modules
- `worker/tasks/embedding_task.py` follows the same pattern

### Knowledge Graph

- `graph_rag/graphiti_service.py` -> `deepfishy/features/knowledge_graph/service.py`
- `graph_rag/entity_types.py` -> `deepfishy/features/knowledge_graph/entity_types.py`

### Infrastructure

- `db/*` -> `deepfishy/infra/db/*`
- `services/minio.py` -> `deepfishy/infra/storage/minio.py`
- `services/milvus.py` -> `deepfishy/infra/vector/milvus.py`
- `services/neo4j.py` -> `deepfishy/infra/graph/neo4j.py`
- `services/embedding_factory.py` and `embedding/*` -> `deepfishy/infra/llm/embedding_factory.py`
- `utils/model_factory.py` and `services/response.py` model bootstrapping -> `deepfishy/infra/llm/chat_factory.py`
- `core/config.py` and `utils/load_config.py` -> `deepfishy/infra/config/settings.py` plus `model_registry.py`
- `core/logging.py` -> `deepfishy/shared/logging.py`

### Shared Utilities

Move only truly generic helpers:

- `utils/serializers.py` -> `deepfishy/shared/serialization.py`
- `utils/load_agents.py` -> `deepfishy/shared/agents.py`
- `core/constants.py` -> `deepfishy/shared/constants.py`
- `utils/pdf_helpers.py`, `utils/pdf_layout.py`, `utils/convert_md_to_pdf.py` -> `deepfishy/shared/pdf/*`

Do not carry over `utils/` as a destination. Every file must be assigned to a specific owning area.

## Implementation Result

The refactor landed in the intended direction:

- `deepfishy.app` now owns API routes, API schemas, and worker task implementations.
- `deepfishy.features.reports` owns report-generation application flows.
- `deepfishy.features.benchmark` owns prompt, evaluator, result parsing, result output, and dataset benchmark flow logic.
- `deepfishy.features.chat` owns chat service, chat runtime bootstrap, and response generation service.
- `deepfishy.features.knowledge_graph` owns the active RAG service implementation.
- `deepfishy.features.ingestion` owns article chunking/embedding preparation logic.
- `deepfishy.infra` owns the active config/model registry, LLM factories, DB/session layer, and external service adapters.
- `deepfishy.shared` owns logging, crawler constants, agent-loading utilities, and shared PDF helpers.

The top-level `api/`, `worker/`, `benchmark/`, `services/`, `core/`, and much of `utils/` remain as compatibility layers so old imports and scripts continue to work.

## Remaining Cleanup Candidates

The structural migration is effectively complete, but these follow-up changes are still possible if the project later wants to remove compatibility layers:

- delete wrapper-only modules once downstream callers are migrated
- move remaining top-level data-oriented helper files only if they still contain non-wrapper runtime logic
- add packaging/CLI entry points so wrapper scripts are no longer needed
- update external documentation and deployment scripts to import `deepfishy.*` directly

## Key Design Decisions

### 1. One Real Package Root

The backend should become importable as `deepfishy.*`.

Why:

- Removes the need for `sys.path.insert(...)`.
- Makes module ownership explicit.
- Lets scripts become thin wrappers around package imports.

Impact:

- `pyproject.toml` must package the new module.
- Existing direct script commands will need updated import-safe entrypoints.

### 2. Centralized Settings and Model Registry

Create:

- `deepfishy/infra/config/settings.py`
- `deepfishy/infra/config/model_registry.py`
- `deepfishy/infra/config/paths.py`

Responsibilities:

- `settings.py` owns environment-backed runtime settings.
- `model_registry.py` owns YAML-backed model definitions and DeepFishy defaults.
- `paths.py` owns project root, outputs directory, benchmark paths, and helper functions for resolving repo-relative paths.

This replaces the current split between `core/config.py`, `utils/load_config.py`, repeated `PROJECT_ROOT` constants, and scattered `os.getenv(...)`.

### 3. Thin Entrypoints

Entry modules should only:

- parse input
- build dependencies
- call feature services
- format output

They should not:

- contain business rules
- decide storage layout
- embed complex report finalization logic
- initialize large global agents at import time

### 4. Report Generation Becomes a Feature, Not a Script

The current report pipeline is the most structurally overloaded part of the repo. It should be decomposed into:

- orchestration building blocks in `features/reports/orchestrators`
- feature tools/prompts/templates in `features/reports/*`
- application services that coordinate report generation and dataset runs
- CLI entrypoints that invoke those services

The citation normalization and final markdown assembly currently buried inside `engine/main.py` should live in a focused report finalization module.

### 5. Chat, Benchmark, and Ingestion Get First-Class Ownership

These are not helpers. They are top-level workflows and should each own their own service layer, DTOs, repositories, and local helpers where needed.

This prevents future spread such as:

- benchmark parsing logic in `utils/`
- chat persistence mixed with route concerns
- worker task logic directly assembling infra dependencies inline

## Target Runtime Responsibilities

### `app/api`

Owns HTTP wiring only:

- router registration
- request/response schemas
- dependency injection
- application factory

### `features/reports`

Owns:

- report generation workflow
- dataset report generation
- output finalization
- report prompts/tools/orchestrators

### `features/benchmark`

Owns:

- benchmark dataset loading
- evaluation prompt construction
- LLM-based scoring flow
- result formatting and persistence

### `features/chat`

Owns:

- conversation lifecycle
- message persistence abstractions
- chat response orchestration

### `features/ingestion`

Owns:

- crawling
- parsing
- chunking
- embedding pipeline application logic

### `infra/*`

Owns:

- external system adapters
- database session management and ORM models
- object storage access
- vector store access
- graph DB access
- model client construction
- runtime configuration

## Phased Migration Plan

This migration is intentionally cleanup-heavy. The goal is a cleaner end state quickly, but each phase should still leave the repo runnable.

### Phase 1: Create the New Package Skeleton

Deliverables:

- Add `deepfishy/` package root with `app/`, `features/`, `infra/`, and `shared/`.
- Move `core/logging.py` into `deepfishy/shared/logging.py`.
- Add `deepfishy/infra/config/paths.py`.
- Update `pyproject.toml` so the package is recognized properly.

Rules:

- No large logic moves yet.
- Add compatibility imports where necessary to reduce breakage during the transition.

Success criteria:

- Imports can begin using `deepfishy.*`.
- No new code relies on `sys.path.insert(...)`.

### Phase 2: Centralize Config and Path Resolution

Deliverables:

- Build `deepfishy/infra/config/settings.py` to replace `core/config.py`.
- Build `deepfishy/infra/config/model_registry.py` to absorb `utils/load_config.py`.
- Replace repeated repo root and output path definitions with `paths.py`.

Migrate first:

- `core/config.py`
- `utils/load_config.py`
- modules with repeated `PROJECT_ROOT` or direct env access used in core flows

Success criteria:

- Main runtime paths resolve through one module.
- Settings are typed and import-safe.
- The number of direct `os.getenv(...)` callsites drops sharply.

### Phase 3: Extract Infrastructure Adapters

Deliverables:

- Move MinIO, Milvus, Neo4j, database models/session, chat/embedding client construction into `deepfishy/infra/*`.
- Consolidate LLM and embedding factories under `infra/llm`.

Refactor targets:

- `services/minio.py`
- `services/milvus.py`
- `services/neo4j.py`
- `services/embedding_factory.py`
- `utils/model_factory.py`
- `services/response.py`
- `db/*`

Success criteria:

- Infra modules no longer live in `services/` or `utils/`.
- Feature modules depend on infra adapters rather than rebuilding clients ad hoc.

### Phase 4: Split `engine/main.py` and Move Reports Into `features/reports`

Deliverables:

- Create report application modules for single-report generation, dataset generation, and finalization.
- Move prompts, tools, orchestrators, templates, and subagent assets into `features/reports`.
- Replace `engine/main.py` with a compatibility shim or delete it after callers migrate.

Cut lines:

- `run_engine(...)` -> `features/reports/application/generate_report.py`
- dataset CSV loop -> `generate_dataset_reports.py`
- markdown concatenation and reference normalization -> `finalize_report.py`

Success criteria:

- Report generation can run without importing a god module.
- File output policy is owned by one place.
- The old `engine/main.py` is no longer a central dependency.

### Phase 5: Move Benchmarking Into `features/benchmark` and a CLI

Deliverables:

- Turn `benchmark/evaluate.py` into feature code under `features/benchmark/`.
- Move prompt text into `features/benchmark/prompts.py`.
- Move combined generation/evaluation orchestration into `app/cli/benchmark.py`.

Additional cleanup:

- Benchmark-only helpers should stop living in `utils/`.
- Data files remain under `benchmark/` or a renamed `data/benchmark/`.

Success criteria:

- Benchmarking is a feature module with a clean CLI, not a script with import hacks.

### Phase 6: Move Chat and Worker Logic Behind Feature Services

Deliverables:

- Move `services/chat.py` into `features/chat`.
- Add a `repository.py` for DB persistence operations.
- Update API routes to depend on feature services only.
- Update worker tasks so they call ingestion/report services rather than assembling everything inline.

Success criteria:

- Routes do not import from script-like workflow modules.
- Worker tasks become thin task wrappers.

### Phase 7: Remove Legacy Buckets and Compatibility Shims

Deliverables:

- Delete or empty `utils/`, `services/`, `core/`, `engine/`, and old top-level runtime scripts once all imports have migrated.
- Update README and developer commands.
- Normalize naming across the repo.

Success criteria:

- The old structure no longer acts as a parallel codebase.
- New contributors can understand the repo by reading the top-level package layout.

## Migration Guardrails

To keep the refactor from turning into chaos:

1. Move one ownership area at a time.
2. Keep public import shims only temporarily and remove them by the end.
3. Do not mix structural moves with behavior changes unless required for extraction.
4. Add smoke tests or command checks after each phase for API startup, benchmark CLI import, and worker initialization.
5. Prefer moving files into their final homes early rather than introducing intermediate “temporary” directories.

## Recommended First Implementation Slice

The highest-leverage first slice is:

1. Create `deepfishy/` package root.
2. Introduce `infra/config/settings.py`, `model_registry.py`, and `paths.py`.
3. Move logging into `shared/logging.py`.
4. Start importing from the new package in one or two core paths.
5. Split `engine/main.py` next, before touching smaller features.

Why this first:

- It fixes the import model and path policy early.
- It gives every later move a stable destination.
- It reduces the chance of doing two migrations for the same files.

## Risks and Mitigations

### Risk: Large import breakage

Mitigation:

- Use temporary compatibility modules during early phases.
- Move modules with clear ownership first.

### Risk: Behavior regressions during structural changes

Mitigation:

- Avoid “clean up while moving” unless the cleanup is required for the move.
- Compare generated outputs before and after the report-pipeline split.

### Risk: The old and new structures both remain active

Mitigation:

- Put a timebox on compatibility shims.
- Explicitly ban new code in legacy buckets once Phase 1 lands.

### Risk: Frontend and Docker references fall behind

Mitigation:

- Treat command updates as part of each relevant phase, not as end-of-project cleanup.

## Out of Scope

This design does not include:

- changing report-generation behavior
- redesigning the frontend
- replacing third-party providers
- rewriting prompts or business logic for quality improvements

Those can happen later, after structural ownership is fixed.

## Acceptance Criteria

This refactor is successful when:

- a new contributor can locate code by feature without learning historical folder lore
- routes, workers, and CLIs are thin wrappers over feature/application services
- infrastructure integrations live under one clear boundary
- `utils/` and `services/` are gone or empty
- `engine/main.py` no longer exists as a core dependency
- import hacks and repeated project-root logic are gone
- config and path resolution are centralized
