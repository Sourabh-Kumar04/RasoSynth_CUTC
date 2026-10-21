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
    ):
        """Execute QLoRA fine-tuning on a dedicated serverless A10G GPU."""
        import json
        from datasets import Dataset
        from trl import SFTTrainer
        from transformers import TrainingArguments
        from unsloth import FastLanguageModel

        print(f"Loading base model {base_model} on NVIDIA A10G...")
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
        model.save_pretrained(f"/tmp/{output_name}")
        tokenizer.save_pretrained(f"/tmp/{output_name}")
        return {"status": "completed", "samples_trained": len(samples)}

except ImportError:
    # Modal not installed locally; file is ready for serverless deployment
    pass
