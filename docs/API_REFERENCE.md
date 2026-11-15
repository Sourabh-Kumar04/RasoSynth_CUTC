# RasoSynthTune API Reference & Specification

Comprehensive REST and WebSocket API specification for RasoSynthTune dataset generation, active learning human review, cryptographic DBOM provenance, and distributed fine-tuning.

---

## 1. Authentication & Security Architecture

All mutating endpoints and protected administrative resources require HTTP Bearer authentication using JSON Web Tokens (JWT) issued by `/auth/login`.

### 1.1 Token Issuance
`POST /auth/login`

Authenticates administrative or standard users and returns a signed HS256 JWT access token.

#### Request Parameters
| Field | Type | Location | Required | Description |
| :--- | :--- | :--- | :--- | :--- |
| `username` | string | Body (JSON) | Yes | Account username (`admin` or standard user). |
| `password` | string | Body (JSON) | Yes | Account password. |

#### Request Body
```json
{
  "username": "admin",
  "password": "your_secure_password"
}
```

#### Response (200 OK)
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsIn...",
  "token_type": "bearer",
  "expires_in": 86400,
  "role": "admin"
}
```

### 1.2 Token Revocation
`POST /auth/logout`

Revokes the bearer token within in-memory process tracking for the duration of the token's lifetime.

---

## 2. System Health, Readiness & Telemetry

System liveness, dependency status, database connectivity, and real-time load telemetry.

### 2.1 Deep System Health Check
`GET /health`

Returns deep health checks across database connections, cache backends, configured inference providers, and system hardware metrics.

#### Response Parameters
| Field | Type | Description |
| :--- | :--- | :--- |
| `status` | string | Overall service health: `healthy`, `degraded`, or `unhealthy`. |
| `version` | string | Application semantic version. |
| `commit_hash` | string | Active short Git commit SHA. |
| `deployment_mode` | string | Execution environment topology (e.g. `standalone`, `docker_compose`). |
| `database` | boolean | Database connection state. |
| `database_engine` | string | Database engine: `supabase_postgresql`, `postgresql`, or `sqlite`. |
| `redis` | boolean | Redis caching tier connection state. |
| `providers` | object | Map of registered model providers to operational status. |
| `system_metrics` | object | Real-time hardware load (`cpu_load_1m`, `memory_used_percent`). |

#### Response (200 OK)
```json
{
  "status": "healthy",
  "version": "2.0.0",
  "commit_hash": "a4f81c2",
  "deployment_mode": "standalone",
  "database": true,
  "database_engine": "supabase_postgresql",
  "redis": true,
  "research_loop_status": "idle",
  "providers": {
    "gemini": "configured",
    "nvidia": "configured",
    "groq": "healthy",
    "vllm": "configured"
  },
  "system_metrics": {
    "cpu_load_1m": 0.42,
    "memory_used_percent": 38.65
  }
}
```

### 2.2 Kubernetes Readiness Probe
`GET /health/ready`

Orchestrator readiness probe validating that critical database dependencies and at least one model routing provider are operational.

#### Response (200 OK)
```json
{
  "ready": true,
  "status": "healthy",
  "database": true,
  "database_engine": "supabase_postgresql",
  "redis": true,
  "providers": {
    "groq": { "status": "healthy", "latency_ms": 85 },
    "openai": { "status": "healthy", "latency_ms": 110 },
    "anthropic": { "status": "healthy", "latency_ms": 140 }
  },
  "checks": {
    "database": "ready",
    "redis": "ready",
    "providers": "ready"
  },
  "timestamp": "2026-11-15T04:00:00.000000Z"
}
```

### 2.3 Container Liveness Probe
`GET /health/live`

Lightweight non-blocking ping verifying event loop responsiveness.

---

## 3. Ingestion & Streaming Endpoints

### 3.1 Streaming Arrow & Parquet Ingestion
`POST /api/v1/datasets/{dataset_id}/import-stream`

Streams Apache Arrow IPC (`.arrow`, `.feather`), Arrow Streaming IPC (`.arrows`), or Apache Parquet (`.parquet`) binary payloads directly into dataset storage in zero-copy chunks.

#### Request Parameters
| Field | Type | Location | Required | Description |
| :--- | :--- | :--- | :--- | :--- |
| `dataset_id` | string | Path | Yes | Target dataset identifier. |
| `format` | string | Query | No | Format: `arrow_stream` (default), `arrow_file`, or `parquet`. |
| `batch_size` | integer | Query | No | Chunk ingestion size (default: `500`). |

#### cURL Example
```bash
curl -X POST "http://localhost:8000/api/v1/datasets/ds-100/import-stream?format=parquet&batch_size=1000" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/octet-stream" \
  --data-binary @samples.parquet
```

---

## 4. Human-in-the-Loop (HITL) Review & Active Learning

Workflows for active learning triage, manual feedback, dataset curation, and preference pair mining.

### 4.1 Prioritized Review Queue
`GET /api/review/queue`

Retrieves candidate review items prioritized by uncertainty sampling or quality heuristics.

#### Query Parameters
| Parameter | Type | Required | Constraints / Default | Description |
| :--- | :--- | :--- | :--- | :--- |
| `strategy` | string | No | `fifo` (default), `uncertainty`, `entropy`, `quality_asc`, `quality_desc` | Prioritization heuristic algorithm. |
| `status` | string | No | `pending`, `in_review`, `approved`, `rejected`, `flagged` | Filter items by current review state. |
| `job_id` | string | No | None | Filter queue to a specific generation job ID. |
| `page` | integer | No | `>= 1` (default: `1`) | Pagination page index. |
| `page_size`| integer | No | `1` to `500` (default: `50`) | Number of records per page. |

#### Response (200 OK)
```json
{
  "items": [
    {
      "id": "rev-1092",
      "job_id": "job-8421",
      "instruction": "What are the ITC conditions under Section 16(2) of the CGST Act?",
      "response": "Tax invoice must be possessed and GSTR-2B details populated...",
      "quality_score": 0.68,
      "hallucination_risk": 0.32,
      "status": "pending",
      "source_citation": "Section 16(2) CGST Act 2017"
    }
  ],
  "total": 142,
  "page": 1,
  "page_size": 50,
  "strategy": "uncertainty"
}
```

### 4.2 Submit Item for Review
`POST /api/review/queue`

Submits an individual synthetic or parsed candidate into the human review queue.

#### Request Body
```json
{
  "instruction": "Explain e-invoicing thresholds under Notification No. 10/2023-CT.",
  "response": "E-invoicing is mandatory for AATO exceeding ₹5 Crore...",
  "job_id": "job-8421",
  "dataset_id": "ds-100",
  "source_url": "https://cbic.gov.in/notifications",
  "source_text": "Central Tax Notification No. 10/2023 issued 10th May 2023",
  "quality_score": 0.82,
  "hallucination_risk": 0.08
}
```

### 4.3 Approve Review Item
`POST /api/review/queue/{item_id}/approve`

Transitions candidate status to `approved`. The reviewer identity is automatically bound from the JWT.

#### Request Body
```json
{
  "notes": "Verified statutory thresholds against CBIC Gazette."
}
```

### 4.4 Reject Review Item
`POST /api/review/queue/{item_id}/reject`

Transitions candidate status to `rejected`, logging structured failure reason codes for feedback stratification.

#### Request Body
```json
{
  "notes": "Outdated threshold cited; omitted Finance Act 2024 amendment.",
  "reason_codes": ["statutory_inaccuracy", "hallucination"]
}
```

### 4.5 Edit & Curate Review Item
`POST /api/review/queue/{item_id}/edit`

Applies authoritative reviewer corrections, creating an implicit chosen/rejected preference pair.

#### Request Body
```json
{
  "edited_instruction": "What is the mandatory e-invoicing threshold for Indian businesses as of August 2023?",
  "edited_response": "As per CBIC Notification No. 10/2023-CT, businesses with AATO exceeding ₹5 Crore in any prior financial year must issue e-invoices.",
  "notes": "Corrected typographical error in notification number.",
  "reason_codes": ["formatting_fix"]
}
```

### 4.6 Queue Telemetry & Statistics
`GET /api/review/stats`

Returns aggregated operational counts across the review pipeline.

#### Response (200 OK)
```json
{
  "total_items": 1250,
  "pending_count": 84,
  "approved_count": 1050,
  "rejected_count": 92,
  "flagged_count": 24,
  "inter_annotator_agreement_kappa": 0.78
}
```

### 4.7 Export Preference Pairs (DPO / ORPO / SimPO)
`GET /api/review/queue/export-dpo`

Streams pairwise preference records mined from reviewer edit actions.

#### Response (200 OK)
```json
{
  "pairs": [
    {
      "prompt": "What is the mandatory e-invoicing threshold?",
      "chosen": "As per CBIC Notification No. 10/2023-CT, businesses exceeding ₹5 Crore...",
      "rejected": "E-invoicing is required for businesses with turnover exceeding 10 Crore...",
      "source_review_id": "rev-1092"
    }
  ],
  "count": 1
}
```

### 4.8 Trigger Closed-Loop Preference Fine-Tuning
`POST /api/review/jobs/{job_id}/trigger-dpo-finetune`

Extracts mined DPO preference pairs for `job_id`, writes a verified JSONL training set, and schedules a fine-tuning job.

---

## 5. Fine-Tuning & Model Management

Job creation, target infrastructure dispatch, real-time telemetry streaming, and VRAM estimation.

### 5.1 Create Fine-Tuning Job
`POST /api/finetune/jobs`

Dispatches a fine-tuning job to the specified compute runtime.

#### Request Parameters
| Field | Type | Required | Constraints / Default | Description |
| :--- | :--- | :--- | :--- | :--- |
| `base_model` | string | Yes | Default: `sarvamai/sarvam-2b-v0.5` | Hugging Face base model identifier. |
| `execution_target` | string | Yes | `local`, `modal`, `colab`, `runpod`, `serverless` | Target execution infrastructure. |
| `dataset_id` | string | No | None | Dataset ID (or provide `dataset_path`). |
| `dataset_path` | string | No | None | Direct filesystem path to training JSONL. |
| `training_method` | string | No | `sft` (default), `dpo`, `orpo`, `kto`, `simpo` | Fine-tuning objective algorithm. |
| `lora_r` | integer | No | `4` to `128` (default: `16`) | LoRA attention rank. |
| `lora_alpha` | integer | No | `4` to `256` (default: `32`) | LoRA alpha scaling parameter. |
| `num_train_epochs`| integer | No | `1` to `100` (default: `3`) | Number of training epochs. |
| `per_device_train_batch_size` | integer | No | `1` to `64` (default: `4`) | Micro-batch size per GPU device. |
| `learning_rate` | float | No | `> 0` (default: `0.0002`) | Initial AdamW optimizer learning rate. |
| `load_in_4bit` | boolean | No | Default: `true` | Enable bitsandbytes QLoRA NF4 quantization. |
| `bf16` | boolean | No | Default: `true` | Use bfloat16 mixed precision. |
| `webhook_url` | string | No | Valid URL | Notification webhook called upon completion or failure. |

#### Request Body
```json
{
  "dataset_id": "ds-100",
  "base_model": "sarvamai/sarvam-2b-v0.5",
  "execution_target": "modal",
  "training_method": "dpo",
  "lora_r": 16,
  "lora_alpha": 32,
  "num_train_epochs": 3,
  "per_device_train_batch_size": 4,
  "learning_rate": 0.0002,
  "load_in_4bit": true,
  "bf16": true,
  "output_model_name": "sarvam-2b-indic-tax-aligned"
}
```

#### Response (201 Created)
```json
{
  "id": "ft-job-9032",
  "status": "pending",
  "base_model": "sarvamai/sarvam-2b-v0.5",
  "execution_target": "modal",
  "training_method": "dpo",
  "created_at": "2026-11-15T04:12:00.000000Z",
  "owner": "admin"
}
```

### 5.2 List and Retrieve Fine-Tuning Jobs
* `GET /api/finetune/jobs` — Lists all fine-tuning jobs (filtered by owner for non-admin callers).
* `GET /api/finetune/jobs/{id}` — Returns status, hyperparameter configuration, and checkpoint paths.
* `DELETE /api/finetune/jobs/{id}` — Cancels an active training run and terminates remote compute pods.

### 5.3 Live Telemetry & Log Streaming
* `GET /api/finetune/jobs/{id}/logs` — Returns the last $N$ lines from the circular memory buffer.
* `WS /api/finetune/jobs/{id}/stream` — WebSocket endpoint broadcasting loss curves, learning rate, GPU memory allocation, and step throughput.

### 5.4 VRAM Requirement Estimator
`POST /api/finetune/estimate-vram`

Computes precise GPU memory breakdown and hyperparameter recommendations for any model and batch size before starting a training run.

#### Request Body
```json
{
  "base_model": "sarvamai/sarvam-2b-v0.5",
  "per_device_train_batch_size": 4,
  "max_seq_length": 2048,
  "lora_r": 16,
  "load_in_4bit": true,
  "training_method": "dpo"
}
```

#### Response (200 OK)
```json
{
  "breakdown": {
    "base_model": "sarvamai/sarvam-2b-v0.5",
    "estimated_parameters_billion": 2.0,
    "weight_memory_gb": 1.1,
    "lora_optimizer_memory_gb": 0.16,
    "activation_memory_gb": 0.64,
    "cuda_overhead_gb": 1.2,
    "total_estimated_vram_gb": 3.1,
    "recommended_gpu_vram_gb": 8.0,
    "supported_on_16gb_gpu": true,
    "supported_on_24gb_gpu": true
  },
  "recommended_hyperparameters": {
    "load_in_4bit": true,
    "bf16": true,
    "per_device_train_batch_size": 4,
    "gradient_accumulation_steps": 4,
    "lora_r": 16,
    "lora_alpha": 32,
    "max_seq_length": 2048
  }
}
```

---

## 6. Cryptographic DBOM & In-Toto Supply-Chain Provenance

Cryptographic Data Bill of Materials (DBOM), SHA-256 Merkle root verification, and ECDSA digital signatures.

### 6.1 Verify Merkle Root Integrity
`POST /api/dbom/verify`

Recomputes the cryptographic SHA-256 Merkle tree root over dataset samples and compares it against the attested certificate root hash.

#### Request Body
```json
{
  "job_id": "job-8421",
  "merkle_root": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
}
```

#### Response (200 OK)
```json
{
  "is_valid": true,
  "verified": true,
  "computed_root": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
  "certificate_root": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
  "sample_count": 500,
  "verified_at": "2026-11-15T04:15:00.000000Z"
}
```

### 6.2 Sign In-Toto Provenance Attestation
`POST /api/dbom/sign`

Generates an in-toto v1.0 supply chain statement over the Merkle root and signs it with an ECDSA SECP256R1 private key.

#### Request Parameters
| Field | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `merkle_root` | string | Yes | SHA-256 Merkle root of the verified samples. |
| `dataset_name` | string | No | Dataset name (default: `dataset`). |
| `sample_count` | integer | No | Total sample count included in the Merkle root. |
| `builder_id` | string | No | Pipeline URI (default: `https://github.com/Sourabh-Kumar04/RasoSynth_CUTC`). |
| `license_type` | string | No | Attested dataset license (default: `PolyForm-Noncommercial-1.0.0`). |

#### Request Body
```json
{
  "merkle_root": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
  "dataset_name": "indic-taxation-v1",
  "sample_count": 500,
  "license_type": "PolyForm-Noncommercial-1.0.0"
}
```

#### Response (200 OK)
```json
{
  "statement": {
    "_type": "https://in-toto.io/Statement/v0.1",
    "predicateType": "https://rasosynthtune.dev/provenance/v1",
    "subject": [
      {
        "name": "indic-taxation-v1",
        "digest": {
          "sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
        }
      }
    ],
    "predicate": {
      "builder": {
        "id": "https://github.com/Sourabh-Kumar04/RasoSynth_CUTC"
      },
      "buildType": "https://rasosynthtune.dev/pipeline/v1",
      "invocation": {
        "sample_count": 500,
        "license": "PolyForm-Noncommercial-1.0.0"
      },
      "metadata": {
        "issued_at": 1731644100.0,
        "dbom_verified": true
      }
    }
  },
  "merkle_root": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
  "signature": "3045022100a7b4...",
  "public_key_pem": "-----BEGIN PUBLIC KEY-----\nMFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAE...\n-----END PUBLIC KEY-----",
  "timestamp": 1731644100.0
}
```

### 6.3 Verify Digital Attestation Signature
`POST /api/dbom/verify-signature`

Validates that an In-Toto statement and Merkle root were signed by the holder of the SECP256R1 public key.
