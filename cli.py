#!/usr/bin/env python3
"""RasoSynthTune Developer CLI.

Unified command-line interface for autonomous synthetic dataset generation,
auditing, benchmarking, and fine-tuning recipe generation:
1. `generate`: Synthesizes high-fidelity datasets with cryptographic DBOM & Nutrition Labels.
2. `audit`: Verifies Merkle tree DBOM integrity, audits benchmark contamination, and scans PII.
3. `benchmark`: Executes the deterministic quality, latency profiling, and ROI benchmark suite.
4. `recipe`: Produces production-ready Unsloth, Axolotl, or Torchtune training recipes.
5. `serve`: Launches the FastAPI canonical backend server.
"""

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).parent.resolve()
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


# Built-in seed exemplar bank for offline and autonomous generation.
# PROVENANCE (P0 honesty): these are hand-written exemplars, NOT sourced
# measurements. The statutory figures inside them (e.g. the 5-crore
# e-invoicing threshold, Rs 20/50-per-day late fees, the 180-day ITC payment
# rule) carry NO date and NO source circular/notification in this file, and
# must NOT be quoted as current law. Verify every statutory figure against
# the current CBIC notifications / CGST Act text before production use. The
# generate command prints this warning on every run (see handle_generate).
BUILTIN_SEED_BANK: Dict[str, List[Dict[str, str]]] = {
    "taxation": [
        {
            "instruction": "What are the core conditions for claiming Input Tax Credit (ITC) under Section 16(2) of the CGST Act?",
            "response": "Under Section 16(2) of the CGST Act 2017, a registered taxpayer can claim ITC only if: 1. They possess a valid tax invoice or debit note. 2. The goods or services have been received. 3. The tax charged has actually been paid to the Government (and reflected in GSTR-2B). 4. They have furnished the return under Section 39 (GSTR-3B). Additional condition: Payment must be made to the supplier within 180 days.",
            "category": "compliance",
            "tier": "3",
        },
        {
            "instruction": "Humari company ka aggregate turnover 12 crore INR hai. Kya humare liye e-invoicing mandatory hai?",
            "response": "Haan, aapke liye e-invoicing mandatory hai. CBIC ke latest notification ke anusar, jin businesses ka aggregate annual turnover kisi bhi financial year me 5 Crore INR se exceed karta hai, unhe B2B supplies aur exports ke liye e-invoices generate karna mandatory hai.",
            "category": "b2b_invoicing",
            "tier": "2",
        },
        {
            "instruction": "Explain the difference between Nil Rated, Exempted, and Zero Rated supplies under GST.",
            "response": "1. Nil Rated Supplies: Goods/services attracting 0% GST rate under schedule. 2. Exempted Supplies: Supplies exempted via specific government notifications under Section 11 of CGST Act; no ITC can be claimed. 3. Zero Rated Supplies: Exports or supplies to SEZ developers/units under Section 16 of IGST Act; full ITC can be claimed or refunded.",
            "category": "definitions",
            "tier": "3",
        },
        {
            "instruction": "What is the late fee penalty for filing GSTR-3B after the due date under Section 47?",
            "response": "For nil tax liability returns, the late fee is Rs 20 per day (Rs 10 CGST + Rs 10 SGST). For returns with tax liability, the late fee is Rs 50 per day (Rs 25 CGST + Rs 25 SGST), subject to statutory turnover-based caps.",
            "category": "statutory_penalties",
            "tier": "2",
        },
        {
            "instruction": "Under what provisions can a GST registration be cancelled suo-moto by the proper officer?",
            "response": "Under Section 29(2) of the CGST Act, a registration may be cancelled if: a taxpayer contravenes prescribed rules, fails to furnish returns for consecutive tax periods (e.g. 6 months for regular taxpayers), does not commence business within 6 months of voluntary registration, or obtained registration by fraud/misstatement.",
            "category": "registration",
            "tier": "4",
        },
    ],
    "general": [
        {
            "instruction": "Define Parameter-Efficient Fine-Tuning (PEFT) and explain why LoRA is widely adopted.",
            "response": "PEFT represents model adaptation techniques that freeze the majority of pretrained parameters and only optimize a small subset of additional weights. LoRA (Low-Rank Adaptation) decomposes dense weight updates into low-rank matrices (A and B), reducing trainable parameter counts by 99% while preserving full model expressive fidelity.",
            "category": "nlp_engineering",
            "tier": "3",
        },
        {
            "instruction": "How does FlashAttention-2 optimize memory access during self-attention computation?",
            "response": "FlashAttention-2 achieves sub-quadratic memory scaling by tiling the Q, K, and V matrices in GPU SRAM, avoiding the materialization of large intermediate N x N attention matrices in High Bandwidth Memory (HBM). It recomputes attention on-the-fly during backpropagation via online softmax rescaling.",
            "category": "systems_ml",
            "tier": "4",
        },
        {
            "instruction": "Explain the role of Merkle trees in verifying data integrity for LLM training pipelines.",
            "response": "A Merkle tree recursively hashes dataset records into parent nodes until a single cryptographic root hash is produced. Any unauthorized alteration, deletion, or corruption of a single token alters downstream hashes and the root, providing mathematical proof of dataset authenticity and provenance.",
            "category": "data_security",
            "tier": "3",
        },
    ],
}


def _load_samples_from_file(file_path: Path) -> List[Dict[str, Any]]:
    """Load records from JSONL, JSON, or Parquet file."""
    if not file_path.exists():
        raise FileNotFoundError(f"Dataset file not found: {file_path}")

    ext = file_path.suffix.lower()
    samples: List[Dict[str, Any]] = []

    if ext == ".jsonl":
        with open(file_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    samples.append(json.loads(line))
    elif ext == ".json":
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            samples = data if isinstance(data, list) else data.get("samples", [data])
    elif ext == ".parquet":
        try:
            import pyarrow.parquet as pq
            table = pq.read_table(str(file_path))
            samples = table.to_pylist()
        except ImportError:
            raise RuntimeError("pyarrow is required to read Parquet datasets.")
    else:
        raise ValueError(f"Unsupported dataset format: {ext}")

    return samples


def handle_generate(args: argparse.Namespace) -> int:
    """Execute dataset generation with DBOM attestation."""
    if args.size < 1:
        print(f"[ERROR] --size must be >= 1 (got {args.size}); refusing to emit an empty dataset.", file=sys.stderr)
        return 1
    from core.export.dbom_attestor import (
        generate_dbom_attestation,
        generate_nutrition_label_markdown,
    )
    from core.validation.indian_pii import mask_indian_pii

    print("=" * 70)
    print("  RasoSynthTune: Autonomous Synthetic Dataset Generator")
    print("=" * 70)
    print(f"Domain:       {args.domain}")
    print(f"Target Size:  {args.size}")
    print(f"Mode:         {args.mode}")
    print(f"Format:       {args.format}")
    print(f"Engine:       {getattr(args, 'engine', 'synthetic')}")
    if getattr(args, 'engine', 'synthetic') not in ("vllm", "ollama"):
        print("Provenance:   TEMPLATE/SEED output — samples are built from the")
        print("              built-in seed bank (BUILTIN_SEED_BANK), not from live")
        print("              model generation or measured data. Statutory figures")
        print("              in seed text are unsourced/undated: verify against")
        print("              current CBIC notifications before production use.")
    print(f"Output Dir:   {args.output_dir}")

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Pick seed bank based on domain keywords
    domain_lower = args.domain.lower()
    if any(k in domain_lower for k in ["tax", "gst", "india", "cgst", "finance"]):
        seed_pool = BUILTIN_SEED_BANK["taxation"]
    else:
        seed_pool = BUILTIN_SEED_BANK["general"]

    engine_choice = getattr(args, "engine", "synthetic")
    samples: List[Dict[str, Any]] = []

    if engine_choice in ["vllm", "ollama"]:
        from providers.core_lib.local_vllm import LocalInferenceEngine

        engine = LocalInferenceEngine(
            engine_type=engine_choice,
            base_url=getattr(args, "engine_url", None),
            model=getattr(args, "model_name", "sarvamai/sarvam-2b-v0.5"),
        )
        print(f"[Engine] Utilizing local {engine_choice.upper()} air-gapped engine at {engine.base_url}")
        if not engine.is_available():
            raise RuntimeError(
                f"Local {engine_choice.upper()} engine at {engine.base_url} is offline or unavailable. "
                "Refusing to write offline echo-template placeholders into dataset rows."
            )
        for i in range(args.size):
            base_item = seed_pool[i % len(seed_pool)]
            prompt = f"Domain: {args.domain}. Task: Formulate an authoritative instruction and answer based on: {base_item['instruction']}"
            res = engine.generate_completion(prompt=prompt)
            if res.get("status") != "live_local" or "Air-gapped local synthetic response for:" in res.get("content", ""):
                raise RuntimeError(
                    f"Local engine returned offline fallback / echo template content ({res.get('status')}). "
                    "Refusing to store echo-template content as real dataset generation."
                )
            inst = f"[{args.domain}] Variant {i + 1}: {base_item['instruction']}" if i >= len(seed_pool) else base_item["instruction"]
            resp = res["content"]
            item_copy = {
                "instruction": mask_indian_pii(inst, replacement_mode="redact"),
                "response": mask_indian_pii(resp, replacement_mode="redact"),
                "domain": args.domain,
                "mode": args.mode,
                "engine": engine_choice,
            }
            samples.append(item_copy)
    else:
        # Synthesize desired count via built-in deterministic bank
        for i in range(args.size):
            base_item = seed_pool[i % len(seed_pool)]
            item_copy = dict(base_item)
            if i >= len(seed_pool):
                item_copy["instruction"] = f"[{args.domain}] Variant {i + 1}: {base_item['instruction']}"
                item_copy["response"] = f"{base_item['response']} (Synthesized for {args.domain} profile {i + 1})."

            # PII check & auto-masking
            item_copy["instruction"] = mask_indian_pii(item_copy["instruction"], replacement_mode="redact")
            item_copy["response"] = mask_indian_pii(item_copy["response"], replacement_mode="redact")
            item_copy["domain"] = args.domain
            item_copy["mode"] = args.mode
            samples.append(item_copy)

    # Export dataset file
    base_name = f"dataset_{args.mode}_{args.size}"
    primary_file = output_dir / f"{base_name}.{args.format}"

    if args.format == "jsonl":
        with open(primary_file, "w", encoding="utf-8") as f:
            for s in samples:
                f.write(json.dumps(s) + "\n")
    elif args.format == "csv":
        import csv
        with open(primary_file, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=list(samples[0].keys()))
            writer.writeheader()
            writer.writerows(samples)
    elif args.format == "parquet":
        try:
            import pyarrow as pa
            import pyarrow.parquet as pq
            table = pa.Table.from_pylist(samples)
            pq.write_table(table, str(primary_file))
        except ImportError:
            # Fail, do NOT write JSONL into a .parquet file: a .parquet file
            # that is not Parquet corrupts every downstream reader silently.
            print("[ERROR] --format parquet requires pyarrow, which is not installed. "
                  "Install pyarrow or choose --format jsonl/csv. No file was written.",
                  file=sys.stderr)
            return 1

    print(f"\n[OK] Synthesized {len(samples)} samples to: {primary_file}")

    # Cryptographic DBOM Attestation
    if args.dbom:
        dbom_cert = generate_dbom_attestation(
            dataset_name=base_name,
            samples=samples,
            domain=args.domain,
            # No compliance flags are stamped: this path runs no contamination
            # check, and PII masking is applied but not verified, so claiming
            # pii_masked/contamination_free would be fabrication.
        )
        dbom_file = output_dir / f"{base_name}.dbom.json"
        with open(dbom_file, "w", encoding="utf-8") as f:
            json.dump(dbom_cert, f, indent=2)
        print(f"[OK] Cryptographic DBOM Certificate:   {dbom_file}")
        print(f"     Merkle Tree SHA-256 Root:        {dbom_cert['merkle_root_hash']}")

        if args.label:
            label_md = generate_nutrition_label_markdown(dbom_cert)
            label_file = output_dir / f"{base_name}.nutrition.md"
            with open(label_file, "w", encoding="utf-8") as f:
                f.write(label_md)
            print(f"[OK] Auditable Data Nutrition Label:    {label_file}")

    print("\nGeneration job completed successfully.")
    return 0


def handle_audit(args: argparse.Namespace) -> int:
    """Audit a dataset for DBOM integrity, PII exposure, and benchmark contamination."""
    from core.export.dbom_attestor import (
        compute_merkle_root,
        compute_sample_hash,
        verify_dataset_dbom,
    )
    from core.evaluation.contamination_checker import check_dataset_contamination
    from core.validation.indian_pii import detect_indian_pii

    print("=" * 70)
    print("  RasoSynthTune: Cryptographic DBOM & Quality Audit Engine")
    print("=" * 70)

    dataset_path = Path(args.dataset)
    print(f"Auditing Dataset: {dataset_path}")

    samples = _load_samples_from_file(dataset_path)
    total_samples = len(samples)
    print(f"Total Samples Loaded: {total_samples}")

    # 1. Merkle Tree & DBOM Verification
    print("\n[1/3] Merkle Tree Cryptographic Integrity...")
    leaf_hashes = [compute_sample_hash(s) for s in samples]
    calculated_merkle = compute_merkle_root(leaf_hashes)

    dbom_verified = None
    dbom_path = Path(args.verify_dbom) if args.verify_dbom else dataset_path.parent / f"{dataset_path.stem}.dbom.json"
    if dbom_path.exists():
        with open(dbom_path, "r", encoding="utf-8") as f:
            dbom_cert = json.load(f)
        verify_res = verify_dataset_dbom(samples, dbom_cert)
        is_valid = verify_res.get("is_valid", False)
        dbom_verified = is_valid
        print(f"      Certificate Found: {dbom_path.name}")
        print(f"      Attestation Root:  {dbom_cert.get('merkle_root_hash')}")
        print(f"      Calculated Root:   {calculated_merkle}")
        print(f"      Status:            {'PASSED - Cryptographically Intact' if is_valid else 'FAILED - ' + str(verify_res.get('status'))}")
    else:
        print(f"      Calculated Merkle Root: {calculated_merkle}")
        print("      (No existing .dbom.json found to verify against; root computed afresh)")

    # 2. PII Exposure Audit
    print("\n[2/3] Statutory PII & Privacy Scan (DPDP Act Compliance)...")
    pii_violations = 0
    pii_types_found: Dict[str, int] = {}
    for s in samples:
        text = f"{s.get('instruction', '')} {s.get('response', '')} {s.get('input', '')}"
        detected = detect_indian_pii(text)
        if detected:
            pii_violations += 1
            for k, vals in detected.items():
                pii_types_found[k] = pii_types_found.get(k, 0) + len(vals)

    if pii_violations == 0:
        print("      Status: PASSED - 0 unmasked statutory PII entities detected.")
    else:
        print(f"      Status: WARNING - {pii_violations} samples contain unmasked PII entities: {pii_types_found}")

    # 3. Benchmark Contamination Audit
    print("\n[3/3] Benchmark Leakage & Contamination Audit...")
    contamination_res = check_dataset_contamination(samples)
    leakage_detected = contamination_res.get("leakage_detected", False)
    flagged = contamination_res.get("flagged_samples", 0)

    if not leakage_detected:
        print("      Status: PASSED - 0% leakage against MMLU, GSM8K, IndicGLUE, ARC.")
    else:
        print(f"      Status: WARNING - {flagged} samples flagged for potential benchmark contamination.")

    # Audit Card Summary
    print("\n" + "=" * 70)
    print("  AUDIT SCORECARD SUMMARY")
    print("=" * 70)
    print(f"  • Total Dataset Records:      {total_samples}")
    print(f"  • SHA-256 Merkle Root:        {calculated_merkle[:20]}...{calculated_merkle[-8:]}")
    print(f"  • DBOM Attestation Match:     {'PASS' if dbom_verified else ('UNCHECKED' if dbom_verified is None else 'FAIL')}")
    print(f"  • PII DPDP Compliance:        {'PASS (Zero Leakage)' if pii_violations == 0 else 'WARNING'}")
    print(f"  • Benchmark Contamination:    {'PASS (Zero Leakage)' if not leakage_detected else 'FLAGGED'}")
    print("=" * 70)

    if args.output:
        report_data = {
            "dataset": str(dataset_path),
            "total_samples": total_samples,
            "merkle_root": calculated_merkle,
            "dbom_verified": dbom_verified,
            "pii_violations": pii_violations,
            "contamination": contamination_res,
        }
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(report_data, f, indent=2)
        print(f"Audit report saved to: {args.output}")

    return 0 if (pii_violations == 0 and not leakage_detected and dbom_verified is not False) else 1


def handle_benchmark(args: argparse.Namespace) -> int:
    """Run QualityBenchmark suite."""
    from research.quality_benchmark import QualityBenchmark

    print("=" * 70)
    print("  RasoSynthTune: Audited Quality & Enterprise Benchmark")
    print("=" * 70)

    if args.sample_size < 1:
        print(f"[ERROR] --sample-size must be >= 1 (got {args.sample_size}).", file=sys.stderr)
        return 1
    bench = QualityBenchmark(config={"sample_size": args.sample_size})
    results = asyncio.run(bench.run_all(sample_size=args.sample_size))

    if args.json:
        print(json.dumps(results, indent=2))
        return 0

    report = bench.generate_report(results)
    print(report)
    return 0


def handle_recipe(args: argparse.Namespace) -> int:
    """Generate fine-tuning configuration script."""
    from core.training.recipe_generator import generate_training_recipe

    print("=" * 70)
    print("  RasoSynthTune: Production Fine-Tuning Recipe Generator")
    print("=" * 70)
    print(f"Framework:    {args.framework}")
    print(f"Base Model:   {args.model}")
    print(f"Dataset Path: {args.dataset}")
    print(f"Task:         {args.task}")

    recipe_info = generate_training_recipe(
        framework=args.framework,
        base_model=args.model,
        dataset_path=args.dataset,
        dataset_type="sft",
    )

    recipe_code = recipe_info.get("content", "")
    target_output = args.output or f"outputs/recipes/{recipe_info.get('filename', 'recipe.txt')}"

    if target_output:
        out_p = Path(target_output)
        out_p.parent.mkdir(parents=True, exist_ok=True)
        with open(out_p, "w", encoding="utf-8") as f:
            f.write(recipe_code)
        print(f"\n[OK] Training recipe written to: {out_p}")
        print(f"     Launch command:            {recipe_info.get('launch_command')}")
    else:
        print("\n" + recipe_code)

    return 0


def handle_publish(args: argparse.Namespace) -> int:
    """Publish dataset and cryptographic DBOM to Hugging Face Hub."""
    from scripts.publish_to_huggingface import publish_dataset_to_hub

    try:
        res = publish_dataset_to_hub(
            dataset_dir=args.dataset_dir,
            repo_id=args.repo_id,
            private=args.private,
            dry_run=args.dry_run,
        )
        print(f"\n[OK] Publish completed: {res.get('status')}")
        return 0
    except Exception as e:
        print(f"\n[ERROR] Failed to publish dataset: {e}")
        return 1


def handle_serve(args: argparse.Namespace) -> int:
    """Launch canonical FastAPI server."""
    try:
        import uvicorn
    except ImportError:
        print("Error: uvicorn is required to run the server. Install via pip install uvicorn.")
        return 1

    print(f"Starting RasoSynthTune API on {args.host}:{args.port} (reload={args.reload})...")
    uvicorn.run("api.server:app", host=args.host, port=args.port, reload=args.reload)
    return 0


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser for RasoSynthTune CLI."""
    parser = argparse.ArgumentParser(
        prog="rasosynthtune",
        description="RasoSynthTune: Autonomous Synthetic Dataset Refinery & Evaluation CLI",
    )
    subparsers = parser.add_subparsers(dest="command", help="Available subcommands")

    # Command 1: generate
    gen_parser = subparsers.add_parser("generate", help="Synthesize datasets with cryptographic DBOM")
    gen_parser.add_argument("--domain", default="Indian Taxation & GST Compliance", help="Target domain")
    gen_parser.add_argument("--size", type=int, default=10, help="Number of samples to synthesize")
    gen_parser.add_argument("--mode", default="distillation", choices=["distillation", "agentic_cot", "contrastive_pairs", "self_correcting", "synthetic"], help="Synthesis mode")
    gen_parser.add_argument("--format", default="jsonl", choices=["jsonl", "parquet", "csv"], help="Export format")
    gen_parser.add_argument("--output-dir", default="outputs", help="Output directory")
    gen_parser.add_argument("--engine", default="synthetic", choices=["synthetic", "vllm", "ollama"], help="Synthesis execution engine")
    gen_parser.add_argument("--engine-url", default=None, help="Base URL for local vLLM / Ollama instance")
    gen_parser.add_argument("--model-name", default="sarvamai/sarvam-2b-v0.5", help="Model name for local engine")
    gen_parser.add_argument("--dbom", dest="dbom", action="store_true", default=True, help="Generate cryptographic DBOM certificate")
    gen_parser.add_argument("--no-dbom", dest="dbom", action="store_false", help="Disable DBOM generation")
    gen_parser.add_argument("--label", dest="label", action="store_true", default=True, help="Generate Data Nutrition Label")
    gen_parser.add_argument("--no-label", dest="label", action="store_false", help="Disable Nutrition Label")

    # Command 2: audit
    audit_parser = subparsers.add_parser("audit", help="Audit dataset DBOM integrity, PII, and contamination")
    audit_parser.add_argument("--dataset", required=True, help="Path to dataset file (JSONL, Parquet, JSON)")
    audit_parser.add_argument("--verify-dbom", default=None, help="Explicit path to .dbom.json certificate")
    audit_parser.add_argument("--output", default=None, help="Path to write JSON audit report")

    # Command 3: benchmark
    bench_parser = subparsers.add_parser("benchmark", help="Run quality, latency, and ROI benchmark suite")
    bench_parser.add_argument("--sample-size", type=int, default=500, help="Benchmark sample corpus size")
    bench_parser.add_argument("--json", action="store_true", help="Output results as JSON")

    # Command 4: recipe
    recipe_parser = subparsers.add_parser("recipe", help="Generate fine-tuning recipes for Axolotl, Unsloth, Torchtune")
    recipe_parser.add_argument("--framework", default="axolotl", choices=["axolotl", "unsloth", "torchtune"], help="Fine-tuning framework")
    recipe_parser.add_argument("--model", default="sarvamai/sarvam-2b-v0.5", help="Pretrained base model identifier")
    recipe_parser.add_argument("--dataset", default="dataset.jsonl", help="Dataset path")
    recipe_parser.add_argument("--task", default="tax_rag_extraction", help="Fine-tuning task description")
    recipe_parser.add_argument("--output", default=None, help="File to write recipe configuration to")

    # Command 5: serve
    serve_parser = subparsers.add_parser("serve", help="Launch FastAPI canonical backend server")
    serve_parser.add_argument("--host", default="0.0.0.0", help="Host interface")
    serve_parser.add_argument("--port", type=int, default=8000, help="Port to bind")
    serve_parser.add_argument("--reload", action="store_true", help="Enable code hot-reloading")

    # Command 6: publish
    publish_parser = subparsers.add_parser("publish", help="Publish dataset and cryptographic DBOM to Hugging Face Hub")
    publish_parser.add_argument("--dataset-dir", required=True, help="Path to directory containing dataset and .dbom.json")
    publish_parser.add_argument("--repo-id", required=True, help="Hugging Face repo id (e.g., rasosynthtune/indic-gst-law-instruct-v1)")
    publish_parser.add_argument("--private", action="store_true", help="Set repository to private")
    publish_parser.add_argument("--dry-run", action="store_true", help="Validate metadata and DBOM without uploading")

    return parser


def main(argv: Optional[List[str]] = None) -> int:
    """Main CLI entry point."""
    parser = build_parser()
    args = parser.parse_args(argv)

    if not args.command:
        parser.print_help()
        return 0

    handlers = {
        "generate": handle_generate,
        "audit": handle_audit,
        "benchmark": handle_benchmark,
        "recipe": handle_recipe,
        "serve": handle_serve,
        "publish": handle_publish,
    }

    return handlers[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
