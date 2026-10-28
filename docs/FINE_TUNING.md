# Fine-tuning — real vs simulated vs template numbers

Read this before quoting any fine-tuning result from the site, a
deck, or a model card.

## Real

- **Local training, `execution_target=local`.** `finetuning/trainer.py`
  runs real PEFT/Unsloth training on local hardware. Loss values,
  adapter weights, and exported artifacts from a local run are real
  for that run — quote them with the run's dataset, base model,
  hardware, and commit.
- **Colab GPU notebook, actually run on a GPU.**
  `finetuning/RasoSynthTune_FineTuning_Colab.ipynb` (Unsloth +
  TRL `SFTTrainer`) produces real adapter weights only when it is
  actually executed on a T4/A100 GPU. Linking the notebook is not a
  training result.
- **API contract.** `api/finetune.py` documents: use `'local'` for
  real PEFT/Unsloth training; `'colab'`/`'modal'`/`'runpod'` may run
  simulated demo paths.

## Simulated (label it simulated, every time)

- **Live-site fine-tuning runs.** On the live site, fine-tuning
  logs say demo placeholders, not GPU-trained weights. Loss curves
  and adapter/GGUF files from those runs are placeholders.
- **Colab bridge.** `finetuning/colab_bridge.py` sets
  `execution_mode: "simulated"`, `is_simulated: true`, and
  `weights_are_placeholders: true`, and appends a model-card
  disclosure: "loss curves and adapter/GGUF files are demo
  placeholders, not GPU-trained weights."
- **Modal stub.** `finetuning/trainer.py` contains a demo stub for
  Modal serverless GPU that "emits simulated progress, not real
  remote training" and completes with "no A10G QLoRA job was run"
  (fixed demo loss values 1.78 → 1.09 → 0.72 in the stub).
- **Any loss curve, adapter file, or GGUF export from a simulated
  run.** Simulated means the numbers illustrate the pipeline's
  shape; they are not measurements of a trained model.

## Template numbers (label them template, or delete them)

- Example hyperparameters in docs and recipes (e.g. `lora_r`,
  epochs, sample counts in example commands) are templates for a
  user to fill in, not results.
- Cost figures on the site do not trace to a real provider bill.
  Do not quote them as spend. A cost claim needs a bill or a
  provider invoice reference.
- Previously published README benchmark figures (uniqueness,
  diversity, cost-per-sample, throughput) were removed in the
  2026-10-28 docs pass because they were not re-traced to a current
  run. Re-add a figure only with its script, commit, and run output.

## How to report a fine-tuning result honestly

State, in one line each: execution target (`local` vs simulated
path), dataset id + DBOM root, base model, hardware (or "simulated,
no GPU"), and whether weights are real or placeholders. If any of
those is missing, the result is not reportable as a training result.

