# 🚀 RasoSynthTune: Live Web Application & CLI Technical Walkthrough

> **Product**: RasoSynthTune 2.0.0 Enterprise  
> **Target Audience**: Technical Evaluators, Enterprise Architects, Venture Partners, and AI Engineers  
> **Frontend Architecture**: Next.js 14 (App Router, React 18, Tailwind CSS, Lucide, GSAP, Radix UI)  
> **Backend Architecture**: FastAPI (Python 3.11+), Celery, SQLAlchemy 2.0 Async, Supabase PostgreSQL, Redis  
> **Estimated Walkthrough Duration**: 5–7 Minutes  
> **License Notice**: Licensed under the [PolyForm Noncommercial License 1.0.0](LICENSE) (strictly non-commercial use).

---

## 📖 Technical Acronym & Core Concept Glossary

Before operating the platform, review the core architectural terms utilized throughout the interface:

| Acronym / Term | Full Name | Technical Definition & System Role |
| :--- | :--- | :--- |
| **DBOM** | **Data Bill of Materials** | A cryptographically verifiable manifest (SHA-256 Merkle tree root) recording dataset lineage, transformation operations, license attributions, and data nutrition metrics for regulatory compliance. |
| **DAG** | **Directed Acyclic Graph** | A mathematical graph of directed edges with no closed loops. RasoSynthTune uses DAGs to model multi-stage data pipelines (Ingestion $\rightarrow$ Hygiene $\rightarrow$ Synthesis $\rightarrow$ Attestation) ensuring deterministic execution without deadlocks. |
| **LoRA** | **Low-Rank Adaptation** | A Parameter-Efficient Fine-Tuning technique that freezes pre-trained model weights and injects trainable rank-decomposition matrices ($W_0 + B \times A$) into transformer attention and feed-forward layers. |
| **PEFT** | **Parameter-Efficient Fine-Tuning** | A library and framework ecosystem that adapts large foundation models by updating only a tiny fraction ($<1\%$) of parameters, minimizing GPU VRAM requirements. |
| **GGUF** | **GPT-Generated Unified Format** | A binary file format optimized for fast loading and edge inference of quantized language models via `llama.cpp` across CPU and consumer GPU hardware. |
| **SimPO** | **Simple Preference Optimization** | A reference-free direct preference optimization algorithm that aligns models using target response length-normalized margins without requiring a separate reference model in VRAM during alignment. |
| **Verhoeff** | **Verhoeff Checksum Algorithm** | A base-10 error detection algorithm based on the dihedral group $D_5$. Utilized in RasoSynthTune's PII engine to mathematically validate and mask 12-digit Indian Aadhaar numbers while detecting all single-digit and adjacent transposition errors. |

---

## 🛠️ Prerequisites & Local Environment Launch

To run the live walkthrough locally, ensure the backend API server and Next.js frontend are active:

### 1. Launch Backend API (Terminal 1)
```bash
# From repository root
cp .env.example .env
pip install -e ".[dev]"
python main.py --host 127.0.0.1 --port 8000
```
*Verify backend health*: Open `http://127.0.0.1:8000/health` (returns JSON status) or `http://127.0.0.1:8000/docs` (Swagger OpenAPI UI).

### 2. Launch Next.js 14 Frontend Dashboard (Terminal 2)
```bash
# From repository root
cd frontend
npm install
npm run dev
```
*Access Web Dashboard*: Open `http://localhost:3000` (or `http://localhost:3001` if port 3000 is occupied).

> [!NOTE]
> If evaluating via the hosted cloud environment, navigate directly to:  
> **Live Demo Portal**: [https://rasosynthtune-indiaai.vercel.app](https://rasosynthtune-indiaai.vercel.app)

---

## 🗺️ Visual Guided Tour: 7 Web Application Modules

```
 ┌────────────────────────────────────────────────────────────────────────┐
 │                    RasoSynthTune 2.0.0 Command Center                  │
 ├───────────┬───────────────┬────────────┬─────────────┬─────────────────┤
 │  Studio   │ Orchestration │ Merkle     │ Quality     │ Review Studio   │
 │  /studio  │ /orchestration│ DBOM /dbom │ /quality    │ /review         │
 ├───────────┴───────────────┴────────────┴─────────────┴─────────────────┤
 │         Blinded Elo Arena (/research)   │  Model Studio (/finetune)    │
 └─────────────────────────────────────────┴──────────────────────────────┘
```

---

### Module 1: Dataset Studio (`/studio`)

**Direct URL**: `http://localhost:3000/studio`  
**Purpose**: Interactive intent extraction, domain configuration, and autonomous dataset synthesis dispatch.

#### Step-by-Step Walkthrough:
1. **Explore 1-Click Industry Presets**:
   - At the top of the Studio canvas, observe the preset banner:
     - `AI Kosh (GST & Indian Tax)`: Targets Section 16(4) CGST Act, ITC reconciliation, and CBIC circulars.
     - `Bharatiya Nyaya Sanhita (BNS)`: Targets criminal jurisprudence and statutory transitions from IPC.
     - `Clinical Emergency Triage`: Targets Bayesian differential diagnosis and Beers criteria.
   - Click on the **AI Kosh (GST & Indian Tax)** card. Observe how the prompt canvas, domain invariants, and preserved statutory terms (`Section 16(4)`, `ITC`, `GSTR-3B`, `GSTR-2B`) automatically populate.
2. **Select Synthesis Engine**:
   - In the **Engine Configuration** panel, select from the 7 specialized synthesis paradigms:
     - **Chain-of-Thought (CoT)**: Step-by-step deductive legal and statutory reasoning.
     - **Socratic Dialectic**: Iterative adversarial questioning exposing boundary conditions.
     - **Preference Alignment (DPO/SimPO)**: Generates paired `chosen` vs. `rejected` completions.
     - **Tool-Calling / Agentic**: JSON function signatures and AST-validated execution calls.
     - **Pedagogical Curriculum**: Tiered difficulty sequencing (Tier 1 Definitions $\rightarrow$ Tier 3 Multi-hop).
3. **Configure Guardrails & Attestation**:
   - Toggle **Mask Indian Statutory PII**: Activates regex and Verhoeff checksum validation across Aadhaar, PAN, and GSTIN entities.
   - Toggle **Cryptographic DBOM Attestation**: Instructs the pipeline to construct a recursive SHA-256 Merkle tree over all generated output samples.
4. **Dispatch Synthesis Job**:
   - Set **Dataset Size** to `100` (for a quick demo run) or `5000`.
   - Click **Generate Dataset**. The interface transitions to the active job viewer with a real-time progress bar and dispatch confirmation.

---

### Module 2: DAG Orchestration & Macro-Pipeline (`/orchestration`)

**Direct URL**: `http://localhost:3000/orchestration`  
**Purpose**: Real-time visual monitoring of the multi-agent Directed Acyclic Graph orchestrator.

#### Step-by-Step Walkthrough:
1. **Select an Active or Completed Job**:
   - Use the job selector dropdown at the top to select the synthesis job dispatched from Studio.
2. **Inspect the 4 Consolidated Macro-Stages**:
   - Observe the horizontal pipeline graph displaying the 4 discrete execution stages:
     1. **Stage 1: Ingestion & Discovery**: Web intelligence agents query trusted legal repositories (e.g., CBIC portals, ITAT gazettes) while enforcing per-domain rate limits.
     2. **Stage 2: Neural Extraction & Hygiene**: Converts raw PDF/HTML into clean text, repairs OCR unicode ligatures, runs MinHash near-duplicate de-duplication, and filters perplexity.
     3. **Stage 3: Autonomous Synthesis**: Multi-agent engines generate domain-grounded instruction pairs with intermediate reasoning traces.
     4. **Stage 4: Cryptographic Packaging & Attestation**: Computes leaf hashes, builds the Merkle tree, evaluates contamination against benchmark splits, and generates the DBOM manifest.
3. **Review Stage Details**:
   - Click on any active or completed node (e.g., **Neural Extraction & Hygiene**).
   - Inspect the sub-processes drawer displaying input source counts, discarded duplicate percentages, and active worker node execution latency.

---

### Module 3: Merkle Tree DBOM & Cryptographic Attestation (`/dbom`)

**Direct URL**: `http://localhost:3000/dbom`  
**Purpose**: Cryptographic provenance verification, tamper-evidence auditing, and data nutrition inspection.

#### Step-by-Step Walkthrough:
1. **Inspect the Cryptographic Certificate**:
   - The top header renders the active certificate card:
     - **Certificate ID**: e.g., `DBOM-AIKOSH-GST-2026-V2`
     - **Root Hash**: Displays the full 64-character hexadecimal SHA-256 Merkle root (e.g., `92f5492d11cd0f6472bb18f4890aade63556e332c75f2f4c86729911265dbb6f`).
     - **Attestation Standard**: Verified compliant with India DPDP Act 2023 & EU AI Act Article 10.
2. **Interact with the Visual Merkle Tree**:
   - Scroll down to the interactive **Merkle Tree Graph** component.
   - Click on the root node to inspect how intermediate branches ($H_{0-1}, H_{2-3}$) recursively aggregate leaf hashes ($h_0, h_1, h_2, h_3$).
   - Click any individual leaf node to reveal the raw sample payload, instruction text, and exact SHA-256 content hash.
3. **Data Nutrition Label**:
   - Review the nutrition card displaying:
     - **Benchmark Contamination**: `0.00%` exact 13-gram overlap against MMLU, GSM8K, and IndicGLUE.
     - **PII Scrubbing Integrity**: `100% Passed` (0 unmasked Aadhaar, PAN, or GSTIN entities).
     - **License Distribution**: 100% Public Gazette / CC-BY compatible.
4. **Download Provenance Artifacts**:
   - Click **Download DBOM Manifest (`dbom.json`)** to inspect the cryptographically signed audit certificate.

---

### Module 4: Neural Quality Inspector (`/quality`)

**Direct URL**: `http://localhost:3000/quality`  
**Purpose**: Multi-dimensional heuristic quality breakdown and interactive LLM-as-a-Judge benchmarking.

#### Step-by-Step Walkthrough:
1. **Inspect 5-Dimensional Heuristic Quality Cards**:
   - **Semantic Groundedness**: Measures fidelity to statutory source text citations ($\ge 0.88$).
   - **Hallucination Risk**: Identifies ungrounded or speculative legal assertions ($< 0.05$).
   - **Lexical Diversity**: Shannon entropy over token n-grams preventing vocabulary collapse.
   - **Toxicity & Safety**: Multi-class safety classification score ($0.00$).
   - **MinHash Uniqueness**: Percentage of unique shingles across the 128-permutation hash space.
2. **Live LLM-as-a-Judge Interactive Evaluator**:
   - Scroll to the **LLM-as-a-Judge Playground** section.
   - The default statutory prompt is pre-loaded:
     > *"Under Indian Medical Council Regulations, what disclosures are mandatory for valid informed consent prior to surgery?"*
   - Click **Run Neural Evaluation**.
   - Review the judge rubric output:
     - **Statutory Grounding Score**: e.g., `9.4 / 10`
     - **Hallucination Likelihood**: `Very Low (0.02)`
     - **Deductive Coherence**: `High (0.95)`
     - **Judge Critique**: Detailed natural language assessment citing specific statutory clauses.

---

### Module 5: Human-in-the-Loop Review Studio (`/review`)

**Direct URL**: `http://localhost:3000/review`  
**Purpose**: Expert human-in-the-loop (HITL) auditing, ground-truth comparison, and line-level editing.

#### Step-by-Step Walkthrough:
1. **Audit the Review Queue**:
   - Review the queue metrics banner: **Pending Review**, **Approved**, **Rejected**, and **Flagged**.
   - Select an item from the review queue table to open the detailed review workspace.
2. **Inspect Dual-Column Grounding**:
   - **Left Column (Source Grounding Anchor)**: Displays the raw statutory excerpt (e.g., Section 16(2)(c) CGST Act gazette text).
   - **Right Column (Synthetic Instruction & Completion)**: Displays the generated training sample.
3. **View Grounding Diff**:
   - Click **Compare Statutory Diff**.
   - The `GroundingDiffModal` highlights additions, deletions, and statutory citations in green and red, ensuring strict fidelity to the legal source text.
4. **Execute Review Action**:
   - Click **Approve (A)**, **Reject (R)**, or click **Edit** to adjust statutory phrasing directly before approving. Notice the status indicator dynamically updates to `approved`.

---

### Module 6: Blinded Elo Arena & Benchmarks (`/research`)

**Direct URL**: `http://localhost:3000/research`  
**Purpose**: Double-blind pairwise human evaluation, Elo rating calibration, and active heuristic controls.

#### Step-by-Step Walkthrough:
1. **Evaluate Blinded Candidate Responses**:
   - Scroll to the **Blinded Pairwise Arena** section.
   - Review the complex domain prompt:
     > *"A registered supplier issued a tax invoice for ₹5,00,000 + 18% GST and received full payment, but failed to file GSTR-3B. Can the recipient claim ITC under Section 16(2)(c) of CGST Act 2017?"*
   - Evaluate **Candidate A** and **Candidate B** side by side. Note that model names, parameters, and origins are completely blinded.
2. **Submit Vote & Trigger Dynamic Elo Calibration**:
   - Click **Vote for Candidate A (Better Grounding)**.
   - **The Reveal**: Candidate identities unmask immediately:
     - **Candidate A**: `sarvamai/sarvam-2b-indic-dpo` (Domain Fine-Tuned Model)
     - **Candidate B**: `Qwen/Qwen2.5-1.5B-Instruct` (Generic Base Model)
   - **Elo Recalibration**: Observe the dynamic Elo delta calculated via standard tournament rules ($K=32$):
     - `sarvam-2b-indic-dpo`: $\mathbf{1248.0 \rightarrow 1264.2}$ ($\mathbf{+16.2}$)
     - `qwen-2.5-7b`: $\mathbf{1215.0 \rightarrow 1198.8}$ ($\mathbf{-16.2}$)
3. **Configure Research Heuristic Toggles**:
   - Scroll to the **Active Research Heuristics** panel.
   - Toggle techniques on/off to customize synthesis behavior:
     - **MinHash De-duplication** (Jaccard similarity threshold 0.85)
     - **Devanagari OCR Ligature Repair** (Normalizes scanned gazettes)
     - **13-gram Benchmark Contamination Guard** (Prevents benchmark test leakage)

---

### Module 7: Fine-Tuning & Model Studio (`/finetune`)

**Direct URL**: `http://localhost:3000/finetune`  
**Purpose**: Parameter-Efficient Fine-Tuning (LoRA/QLoRA), serverless Cloud GPU training dispatch, and GGUF quantization.

#### Step-by-Step Walkthrough:
1. **Select Base Model & Dataset**:
   - **Base Model**: Select `sarvamai/sarvam-2b-v0.5`, `meta-llama/Llama-3.2-1B-Instruct`, or `unsloth/llama-3-8b-Instruct`.
   - **Training Dataset**: Select your verified dataset generated in Module 1.
2. **Choose Execution Target**:
   - **Local PEFT / Unsloth**: Executes directly on local workstation hardware via PyTorch.
   - **Serverless Modal A10G Cloud GPU**: Dispatches fine-tuning to a remote NVIDIA A10G (24GB VRAM) container with zero local driver configuration.
3. **Configure Hyperparameters**:
   - Set **LoRA Rank ($r$)**: `16`
   - Set **LoRA Alpha ($\alpha$)**: `32`
   - Set **Training Method**: `sft` (Supervised Fine-Tuning) or `simpo` / `dpo` (Preference Alignment).
4. **Monitor Live Training Telemetry**:
   - Click **Launch Fine-Tuning Run**.
   - Observe the live telemetry chart tracking training loss across epochs, learning rate decay, and step throughput.
   - Upon completion, the engine packages real **SafeTensors** adapter weights (`adapter_model.safetensors`, `adapter_config.json`) available for immediate download or 1-click Hugging Face Hub export.

---

## 💻 CLI Parallel Execution Reference

All workflows demonstrated in the web interface can also be executed headlessly via the canonical `rasosynthtune` CLI:

```bash
# 1. Synthesize 10 GST instruction pairs with DBOM certificate
rasosynthtune generate \
  --domain "Indian Taxation & GST Compliance" \
  --size 10 \
  --format jsonl \
  --synthesis-mode cot

# 2. Audit exported dataset for DBOM Merkle integrity and Verhoeff PII masking
rasosynthtune audit --dataset outputs/dataset.jsonl

# 3. Generate a fine-tuning recipe (Unsloth / Axolotl)
rasosynthtune recipe \
  --framework unsloth \
  --model "sarvamai/sarvam-2b-v0.5" \
  --dataset outputs/dataset.jsonl

# 4. Quantize fine-tuned adapter to edge 4-bit GGUF format
rasosynthtune quantize \
  --model-path outputs/model \
  --quantization-format gguf \
  --bits 4

# 5. Execute automated LLM-as-a-judge comparison
rasosynthtune judge \
  --aligned-model outputs/model \
  --base-model meta-llama/Llama-3.2-1B-Instruct \
  --domain "Indian Taxation & GST Compliance"
```

---

## 📊 Empirical Evaluation & Pilot Caveats

In a small-sample statutory evaluation pilot conducted on `sarvamai/sarvam-2b-v0.5` ($n=5$ held-out statutory evaluation pairs, recorded 2026-10-20):
- **chrF Character Overlap**: Improved from `14.80` to **`94.33`** (+537.4% relative gain).
- **Mean Token-F1**: Improved from `0.191` to **`0.739`** (+286.9% relative gain).
- **Exact Match (EM)**: Increased from `0.0%` to **`40.0%`**.
- **Citation Grounding**: 100% of validated responses correctly cited relevant sections of the CGST Act 2017.

> [!NOTE]
> *Empirical Caveat*: These figures represent a small-sample exploratory pilot ($n=5$), not a statistically scaled benchmark across the entire tax code. Re-evaluate on larger held-out splits using `python scripts/demo_finetune_eval.py` before deploying in production compliance workflows.
