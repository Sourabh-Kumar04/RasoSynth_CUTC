# RasoSynthTune API Reference & Specification

Comprehensive REST & WebSocket API specification for RasoSynthTune dataset generation, active learning review, fine-tuning, and model deployment.

---

## 1. Authentication & Security

All mutating endpoints and protected queries require a Bearer token obtained from `/auth/login`.

```bash
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "your_secure_password"}'
```

Response:
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsIn...",
  "token_type": "bearer",
  "expires_in": 86400,
  "role": "admin"
}
```

---

## 2. Ingestion & Streaming Endpoints

### Streaming Arrow & Parquet Ingestion
`POST /api/v1/datasets/{dataset_id}/import-stream`

Streams Apache Arrow IPC (`.arrow`, `.feather`), Arrow Streaming IPC (`.arrows`), or Apache Parquet (`.parquet`) binary payloads directly into the dataset samples table in zero-copy chunks.

**Headers:**
- `Content-Type: application/octet-stream` (or `application/x-parquet`)
- `Authorization: Bearer <TOKEN>`

**Parameters:**
- `dataset_id` (path, string): Unique dataset identifier.
- `format` (query, string): `arrow_file`, `arrow_stream`, or `parquet`. Default: `arrow_stream`.
- `batch_size` (query, integer): Chunk ingestion batch size. Default: `500`.

**cURL Example:**
```bash
curl -X POST "http://localhost:8000/api/v1/datasets/ds-100/import-stream?format=parquet&batch_size=1000" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/octet-stream" \
  --data-binary @my_data.parquet
```

---

## 3. Review Queue & Active Learning Endpoints

### Prioritized Review Queue
`GET /api/review/queue`

Fetches review candidates sorted by active learning heuristics.

**Query Parameters:**
- `strategy`:
  - `uncertainty` (Default): Prioritizes samples with highest LLM uncertainty & entropy.
  - `entropy`: Highest prediction entropy.
  - `quality_asc`: Lowest quality score first (immediate defect review).
  - `quality_desc`: Highest quality score first.
  - `fifo`: Creation order.
- `status`: `pending`, `in_review`, `approved`, `rejected`, `flagged`.
- `job_id`: Filter by job ID.
- `page`: Page number (1-based).
- `page_size`: Default `20`.

### Export Mined DPO / ORPO Preference Pairs
`GET /api/review/queue/export-dpo`

Streams pairwise preference records mined from human reviewer edits.

**cURL Example:**
```bash
curl -X GET "http://localhost:8000/api/review/queue/export-dpo?job_id=job-123" \
  -H "Authorization: Bearer $TOKEN"
```

**Response Format:**
```json
{
  "pairs": [
    {
      "prompt": "Evaluate patient symptoms of acute asthma.",
      "chosen": "Administer nebulized albuterol and evaluate peak expiratory flow.",
      "rejected": "Advise room rest and observe for 2 hours.",
      "source_review_id": "rev-001"
    }
  ],
  "count": 1
}
```

### Closed-Loop DPO Alignment Trigger
`POST /api/review/jobs/{job_id}/trigger-dpo-finetune`

Extracts mined reviewer edits for `job_id`, writes a verified JSONL training dataset, and launches a fine-tuning job.

**Request Body:**
```json
{
  "base_model": "sarvamai/sarvam-2b-v0.5",
  "training_method": "dpo",
  "output_model_name": "dpo-sarvam-aligned",
  "num_train_epochs": 3,
  "learning_rate": 0.0002,
  "lora_r": 16,
  "lora_alpha": 32
}
```

---

## 4. Fine-Tuning & Model Management Endpoints

### Interactive VRAM Requirement Estimator
`POST /api/finetune/estimate-vram`

Computes precise GPU memory breakdown and hyperparameter recommendations for any model and batch size.

**Request Body:**
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

**Response:**
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

### Post-Training Benchmark Evaluation
`GET /api/finetune/jobs/{job_id}/benchmark`

Evaluates the fine-tuned model against its base model on formatting compliance, grounding faithfulness, and win rate.

### Multi-Engine Deployment Bundle Export
`POST /api/finetune/jobs/{job_id}/export-bundle`

Generates ready-to-run configurations for vLLM or Ollama.
- `format=vllm`: Safetensors adapter configuration and server launch command.
- `format=ollama`: Quantized GGUF artifact and custom Modelfile.

---

## 5. Review Calibration & Drift Auditing

### Inter-Annotator Calibration Audit
`POST /api/review/calibration/drift-audit`

Audits agreement among human annotators and dynamic LLM judges using Cohen's Kappa $\kappa$. Emits warning events when $\kappa < 0.60$.
