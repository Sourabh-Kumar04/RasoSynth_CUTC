"""
Serverless Cloud GPU Fine-Tuning with Modal.

Run on demand with zero infrastructure management:
    modal run finetuning/modal_trainer.py --dataset-path outputs/dataset.jsonl --base-model unsloth/llama-3-8b-Instruct
"""

import os

try:
    import modal
    app = modal.App("rasosynthtune-finetune")

    # Define container image with CUDA + Unsloth
    image = (
        modal.Image.debian_slim(python_version="3.11")
        .apt_install("git")
        .pip_install(
            "torch",
            "transformers",
            "datasets",
            "accelerate",
            "peft",
            "trl",
            "bitsandbytes",
            "unsloth",
        )
    )

    @app.function(
        image=image,
        gpu="A10G",
        timeout=3600,
        secrets=[modal.Secret.from_name("huggingface-secret", required=False)],
    )
    def train_remote(
        dataset_content: str,
        base_model: str = "unsloth/llama-3-8b-Instruct",
        num_epochs: int = 3,
        lora_r: int = 16,
        lora_alpha: int = 32,
        output_name: str = "rasosynthtune-lora",
        training_method: str = "sft",
        dpo_beta: float = 0.1,
    ):
        """Execute QLoRA or DPO fine-tuning on a dedicated serverless A10G GPU."""
        import json
        from datasets import Dataset
        from transformers import TrainingArguments
        from unsloth import FastLanguageModel

        print(f"Loading base model {base_model} on NVIDIA A10G (method={training_method})...")
        model, tokenizer = FastLanguageModel.from_pretrained(
            model_name=base_model,
            max_seq_length=2048,
            load_in_4bit=True,
        )

        model = FastLanguageModel.get_peft_model(
            model,
            r=lora_r,
            lora_alpha=lora_alpha,
            lora_dropout=0,
            target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
        )

        samples = [json.loads(line) for line in dataset_content.strip().split("\n") if line.strip()]

        if training_method.lower() in ("dpo", "orpo"):
            from trl import DPOTrainer, DPOConfig
            dpo_pairs = []
            for s in samples:
                p = s.get("prompt") or s.get("instruction") or ""
                c = s.get("chosen") or ""
                r = s.get("rejected") or ""
                if p and c and r:
                    dpo_pairs.append({"prompt": str(p), "chosen": str(c), "rejected": str(r)})
            hf_dataset = Dataset.from_list(dpo_pairs)
            trainer = DPOTrainer(
                model=model,
                ref_model=None,
                tokenizer=tokenizer,
                train_dataset=hf_dataset,
                args=DPOConfig(
                    output_dir="/tmp/output",
                    beta=dpo_beta,
                    per_device_train_batch_size=2,
                    gradient_accumulation_steps=8,
                    num_train_epochs=num_epochs,
                    learning_rate=1e-4,
                    fp16=True,
                    logging_steps=10,
                ),
            )
        else:
            from trl import SFTTrainer
            texts = [
                f"### Instruction:\n{s.get('instruction','')}\n\n### Response:\n{s.get('output', s.get('response',''))}{tokenizer.eos_token}"
                for s in samples
            ]
            hf_dataset = Dataset.from_dict({"text": texts})

            trainer = SFTTrainer(
                model=model,
                tokenizer=tokenizer,
                train_dataset=hf_dataset,
                dataset_text_field="text",
                max_seq_length=2048,
                args=TrainingArguments(
                    per_device_train_batch_size=4,
                    gradient_accumulation_steps=4,
                    num_train_epochs=num_epochs,
                    learning_rate=2e-4,
                    fp16=True,
                    logging_steps=10,
                    output_dir="/tmp/output",
                ),
            )
        trainer.train()
        print("Training complete! Saving model...")
        out_target = f"/tmp/{output_name}"
        model.save_pretrained(out_target)
        tokenizer.save_pretrained(out_target)
        return {"status": "completed", "samples_trained": len(samples), "training_method": training_method}

except ImportError:
    # Modal not installed locally; file is ready for serverless deployment
    pass
