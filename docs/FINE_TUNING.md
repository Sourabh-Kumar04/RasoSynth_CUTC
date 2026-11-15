# Model Fine-Tuning & Alignment Engine Specification

RasoSynthTune provides a parameter-efficient fine-tuning (PEFT) and preference alignment engine for large language models (1.7B–9B parameters). The engine supports local NVIDIA GPU execution, headless Google Colab bridge runs, and remote serverless execution on Modal NVIDIA A10G GPUs.

---

## 1. Architecture & Execution Targets

Training jobs are submitted via `POST /api/finetune/jobs` and dispatched to one of three execution targets determined by the `execution_target` field:

| Target | Backend Module | Hardware Profile | Artifact Authenticity |
| :--- | :--- | :--- | :--- |
| `modal` | `finetuning/modal_trainer.py` | NVIDIA A10G (24GB VRAM) Serverless Cloud | Real GPU weights & verified GGUF |
| `local` | `finetuning/trainer.py` | Host NVIDIA GPU (CUDA / ROCm) or CPU | Real weights (GPU) / Fallback CPU |
| `colab` | `finetuning/colab_bridge.py` | Google Colab GPU (T4 / A100 / V100) | Real weights when notebook executed |

If `execution_target` is omitted, the API defaults to `"modal"` when `MODAL_TOKEN_ID` and `MODAL_TOKEN_SECRET` are present in the environment; otherwise, it defaults to `"local"`.

---

## 2. Serverless Modal A10G QLoRA Engine

### 2.1 Environment Setup & Authentication
Remote execution on Modal requires authenticated API credentials in the API server environment:

```env
MODAL_TOKEN_ID=ak-xxxxxxxxxxxxxxxxxxxx
MODAL_TOKEN_SECRET=as-xxxxxxxxxxxxxxxxxxxx
HF_TOKEN=hf_xxxxxxxxxxxxxxxxxxxx          # Required for gated models (e.g. Llama-3.1)
```

The serverless container runs Debian Slim Python 3.11 with CUDA acceleration, `torch`, `transformers`, `datasets`, `accelerate`, `peft`, `trl`, `bitsandbytes`, and `unsloth`.

### 2.2 Automated Hardware & Loader Selection
The remote worker (`modal_trainer.py::train_remote`) applies the following automated hierarchy for model loading:
1. **Unsloth FastLanguageModel**: Loads 4-bit quantized base models (`load_in_4bit=True`) with kernel optimizations and RoPE scaling.
2. **HuggingFace Transformers + PEFT Fallback**: If Unsloth is incompatible with the selected model architecture, the worker automatically falls back to `AutoModelForCausalLM` with `BitsAndBytesConfig`:
   - `bnb_4bit_quant_type="nf4"`
   - `bnb_4bit_compute_dtype=torch.float16`
   - `device_map="auto"`
3. **Dynamic Projection Layer Introspection**: Target projection modules are introspected across model families (Llama, Mistral, Gemma 2, Qwen 2.5, Phi-3, Sarvam) targeting `q_proj`, `k_proj`, `v_proj`, `o_proj`, `gate_proj`, `up_proj`, and `down_proj`.
4. **Attention Backend Selection**: FlashAttention-2 is loaded if compute capability >= 8.0 (Ampere/Ada/Hopper); otherwise falls back to PyTorch SDPA (`scaled_dot_product_attention`).

### 2.3 Training & Alignment Algorithms
The engine supports five optimization algorithms via the `training_method` parameter:

- **SFT (`sft`)**: Supervised Fine-Tuning using TRL `SFTTrainer` with formatted instruction prompt templates.
- **DPO (`dpo`)**: Direct Preference Optimization comparing `chosen` vs `rejected` completions with reference-free sigmoid loss.
- **SimPO (`simpo`)**: Simple Preference Optimization applying length-normalized implicit reward without a reference model (`dpo_loss_type="simpo"`).
- **KTO (`kto`)**: Kahneman-Tversky Optimization applying binary utility optimization (`label: bool`) on desirable and undesirable completions.
- **ORPO (`orpo`)**: Odds Ratio Preference Optimization combining cross-entropy and odds-ratio penalty in a single training objective.

### 2.4 Remote Adapter Retrieval & Packaging
1. Upon training completion, the remote container saves the adapter weights (`adapter_model.safetensors`), LoRA configuration (`adapter_config.json`), and tokenizer configs to `/tmp/{output_name}`.
2. The directory is archived into an in-memory zip payload and returned to the API server as a base64 string (`adapter_zip_base64`).
3. The API server decodes the payload, extracts the files into `outputs/finetune/{job_id}/`, verifies artifact hashes, and packages a standardized distribution archive (`finetuned_model_lora.zip`).

---

## 3. GGUF Conversion & Ollama Modelfile Export

Every successful fine-tuning run produces quantization binaries and serving manifests for edge inference:

### 3.1 GGUF v3 Quantization
The engine produces a compliant GGUF v3 binary (`model-q4_k_m.gguf`):
- Magic bytes: `0x47 0x47 0x55 0x46` (`GGUF\x03\x00\x00\x00`)
- Standardized metadata KV pairs: `general.architecture`, `general.name`, and `general.file_type=15` (Q4_K_M).
- Strict 32-byte memory alignment for tensor offset compatibility with `llama.cpp` and vLLM.

### 3.2 Ollama Modelfile Generation
The export utility (`export_to_ollama`) compiles an edge deployment manifest:

```dockerfile
# Ollama Modelfile for rasosynth-sarvam-2b-instruct
FROM /absolute/path/to/outputs/finetune/job-id
TEMPLATE """{{ if .System }}<|im_start|>system
{{ .System }}<|im_end|>
{{ end }}{{ if .Prompt }}<|im_start|>user
{{ .Prompt }}<|im_end|>
{{ end }}<|im_start|>assistant
{{ .Response }}<|im_end|>"""
PARAMETER temperature 0.7
PARAMETER top_p 0.9
PARAMETER stop <|im_end|>
PARAMETER stop </s>
SYSTEM """You are a domain-specialized AI assistant aligned with RasoSynthTune."""
```

To register and execute the model in Ollama:
```bash
ollama create custom-model -f outputs/finetune/{job_id}/Modelfile
ollama run custom-model
```

### 3.3 Standalone Export Bundle Endpoint
Deployment bundles can be retrieved programmatically via:
```http
POST /api/finetune/jobs/{job_id}/export-bundle?format=gguf
POST /api/finetune/jobs/{job_id}/export-bundle?format=vllm
```

---

## 4. Supported Base Models Catalogue

| Model ID | Parameter Count | Context Window | Default Chat Template | GPU Requirement |
| :--- | :--- | :--- | :--- | :--- |
| `sarvamai/sarvam-2b-v0.5` | 2B | 2048 | `chatml` | CPU / 8GB VRAM |
| `HuggingFaceTB/SmolLM2-1.7B-Instruct` | 1.7B | 2048 | `chatml` | CPU / 8GB VRAM |
| `google/gemma-2-2b-it` | 2B | 4096 | `chatml` | CPU / 8GB VRAM |
| `microsoft/Phi-3-mini-4k-instruct` | 3.8B | 4096 | `chatml` | CPU / 12GB VRAM |
| `ai4bharat/Airavata` | 7B | 4096 | `alpaca` | 16GB VRAM (A10G) |
| `unsloth/mistral-7b-v0.3` | 7B | 8192 | `chatml` | 16GB VRAM (A10G) |
| `Qwen/Qwen2.5-7B-Instruct` | 7B | 8192 | `chatml` | 16GB VRAM (A10G) |
| `meta-llama/Meta-Llama-3.1-8B-Instruct` | 8B | 8192 | `llama3` | 24GB VRAM (A10G) |
| `unsloth/gemma-2-9b` | 9B | 8192 | `chatml` | 24GB VRAM (A10G) |

---

## 5. Result Reporting Standards

When documenting fine-tuning results, every benchmark report must include:
1. **Execution Target**: `modal` (A10G), `local` (hardware spec), or `colab` (GPU model).
2. **Dataset Traceability**: Dataset Version ID, record count, and cryptographic Merkle root hash from the DBOM audit ledger.
3. **Hyperparameters**: Base model ID, LoRA Rank ($r$), Alpha ($\alpha$), learning rate, batch size, gradient accumulation steps, and loss type.
4. **Loss Measurements**: Final training loss and evaluation loss across global steps.
