# Duplication Catalogue & Canonical Module Homes

This document catalogues all module and package duplications, compatibility shims,
and overlapping abstractions in the RasoSynthTune codebase, declaring exactly **one
canonical home** for each.

---

## 1. SDK Package: `rasosynthtune` vs `rasosynth`

- **Canonical Home**: `rasosynthtune` (`rasosynthtune/client.py`, `rasosynthtune/__init__.py`)
- **Compatibility Shim**: `rasosynth` (`rasosynth/client.py`, `rasosynth/__init__.py`)
- **Policy**: All new features, types, and SDK methods must be added exclusively to
  `rasosynthtune`. `rasosynth` re-exports from `rasosynthtune` solely for backwards
  compatibility with historical 1.x imports.

---

## 2. Database & Migrations: `core` vs `db`

- **Canonical Home**: `core` (`core/db.py`, `core/async_db.py`, `core/migration_safety.py`)
- **Compatibility Shim**: `db` (`db/__init__.py`, `db/async_db.py`, `db/migration_safety.py`)
- **Policy**: Database models (`Job`, `Dataset`, `Sample`, etc.), ORM operations,
  and transaction-wrapped migration utilities reside in `core`. The `db/` root package
  is a compatibility layer that forwards imports to `core`.

---

## 3. Orchestration: `core.orchestrator_core` vs `core.orchestrator_pkg`

- **Canonical Home (Engine & Workflow State)**: `core/orchestrator_core.py`
  (`DatasetOrchestrator`, `AgentState`, `Job`, `JobStatus`, `ConstraintAnalysis`)
- **Canonical Home (Checkpoints & Resume)**: `core/orchestrator_pkg/checkpoints.py`
  (`CheckpointManager`, `CheckpointStore`, `CheckpointStage`, `ProviderContext`) and
  `core/orchestrator_pkg/resume.py` (`ResumeStrategy`, `WorkflowResumer`)
- **Policy**: `core/orchestrator_pkg/__init__.py` serves as the unifying facade that
  re-exports the canonical orchestrator classes from `core.orchestrator_core` alongside
  checkpoint management. Direct imports of `DatasetOrchestrator` should target
  `core.orchestrator_core`.

---

## 4. Observability: `core.observability_manager` vs `core.observability`

- **Canonical Home (Manager Facade)**: `core/observability_manager.py` (`ObservabilityManager`)
- **Canonical Home (Telemetry Subsystems)**: `core/observability/`
  (`StructuredLogger`, `DistributedTracer`, `GPUMonitor`, `AIAnalyticsEngine`, `CostTracker`)
- **Policy**: `core/observability_manager.py` coordinates Prometheus metric registration
  and centralized trace dispatch. Detailed logging, tracing, metrics collectors, and
  dashboards live in the `core/observability` submodules.

---

## 5. Security & Secrets: `core.secrets` vs `core.security`

- **Canonical Home (Secrets Providers)**: `core/secrets.py`
  (`SecretsManager`, `EnvironmentSecretsProvider`, `VaultSecretsProvider`, `AWSSecretsProvider`)
- **Canonical Home (Crypto & Authentication Tokens)**: `core/security.py`
  (`SecurityManager`, `Fernet` token encryption, credential masking, password verification)
- **Policy**: External secret retrieval belongs in `core/secrets.py`. Cryptographic
  primitives, field encryption, and token handling belong in `core/security.py` and
  `api/auth.py`.

---

## 6. User Intent: `core.intent` vs `core.intent_extractor`

- **Canonical Home (Data Model)**: `core/intent.py` (`UserIntent`, `IntentExtractionError`)
- **Canonical Home (Extraction Logic)**: `core/intent_extractor.py` (`IntentExtractor`, LLM prompts)
- **Policy**: Data contracts and serialization live in `core/intent.py`. Prompt engineering,
  parsing algorithms, and provider routing for intent extraction live in `core/intent_extractor.py`.

---

## 7. AI Provider Capabilities: `providers.core_lib.base` vs `providers.migration`

- **Canonical Home**: `providers.core_lib.base.ProviderCapability`
- **Policy**: All capabilities (generation, embeddings, streaming, tool-calling, json-mode, etc.)
  must be defined in the canonical `ProviderCapability` enum. `providers/migration.py`
  imports from `providers.core_lib.base` without re-declaring divergent enums.
