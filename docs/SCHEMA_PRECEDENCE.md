# Schema and Migration Precedence Specification

This document defines the authoritative contract for schema management, migrations, and model declarations across RasoSynthTune.

## 1. Precedence Hierarchy

The schema sources are ordered as follows:

1. **SQLAlchemy ORM Models (`core/db.py`)** — **Primary Source of Truth (Top Precedence)**
   - All persistent tables, columns, constraints, foreign keys, and indexes required by runtime business logic MUST be explicitly declared on SQLAlchemy ORM model classes (`Job`, `Dataset`, `FineTuneJob`, `ReviewQueueItem`, etc.).
   - Model definitions govern runtime typing, attribute access, and serialisation (`to_dict()`).

2. **Safe Schema Migrations (`core/migration_safety.py` & `DatabaseManager.create_tables`)** — **Deployment Evolution Layer (Second Precedence)**
   - Used for evolving running deployments (both persistent SQLite and PostgreSQL).
   - Any column added via migrations or safe ALTER statements MUST also be declared in the ORM models so runtime entities can safely read and write it without discrepancy.
   - Idempotent: `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` or SQLite PRAGMA checks ensure existing tables receive new columns without destructive recreation.

3. **Static Initialization Scripts (`init.sql`)** — **Bootstrap Baseline (Lowest Precedence)**
   - `init.sql` serves as the cold-start baseline for container initialization (e.g. Postgres Docker containers).
   - Any addition to ORM models and safe migrations should be mirrored in `init.sql` for consistency, but the ORM and migration layer take precedence at application startup (`Base.metadata.create_all` and safe migration steps).

---

## 2. Multi-Tenancy & NULL-Owner Contract

### Owner Column
- The `owner` column (`String`, indexed, nullable) is maintained on tenant-owned resources:
  - `jobs.owner`
  - `datasets.owner`
  - `finetune_jobs.owner`
  - `review_queue.owner` (inherits from associated job or submitter)

### Backfill & Legacy Single-Tenant Rule
- **Rule**: Existing legacy rows created prior to multi-tenancy have `owner = NULL`.
- **Policy**: `NULL`-owner rows represent legacy single-tenant resources. Under the active tenant security model:
  - **ADMIN** users have unrestricted visibility and access to all rows, including all `NULL`-owner legacy rows and any tenant's rows.
  - **Regular users (USER role)** may only access rows that explicitly belong to their `username` (`owner == current_user.username`). A regular user cannot read, cancel, mutate, export, or download another user's rows or unassigned legacy `NULL`-owner rows.
  - When a resource belongs to another user or is an unowned legacy row accessed by a non-admin, the API returns **404 Not Found** (preventing existence leakage).

---

## 3. Existence Leakage & Error Policy

- When a non-ADMIN user requests a resource (Job, Dataset, FineTuneJob, Review item, Checkpoint) that exists in the database but belongs to a different owner, the route returns **404 Not Found** rather than 403 Forbidden. This ensures zero existence leakage across tenant boundaries.
- **403 Forbidden** is reserved exclusively for role-based permission failures (e.g. a `VIEWER` attempting a write action like `POST /jobs` or `DELETE /jobs/{id}`).
