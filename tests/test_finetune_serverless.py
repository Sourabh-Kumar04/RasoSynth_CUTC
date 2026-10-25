import pytest
from api.finetune import CreateFineTuneJobRequest
from finetuning.trainer import FineTuneConfig, Trainer


def test_create_finetune_request_with_execution_target():
    req = CreateFineTuneJobRequest(
        dataset_path="outputs/test.jsonl",
        base_model="sarvamai/sarvam-2b-v0.5",
        execution_target="modal",
    )
    assert req.execution_target == "modal"

    req_runpod = CreateFineTuneJobRequest(
        dataset_path="outputs/test.jsonl",
        base_model="sarvamai/sarvam-2b-v0.5",
        execution_target="runpod",
    )
    assert req_runpod.execution_target == "runpod"


def test_finetune_config_preserves_execution_target():
    cfg = FineTuneConfig(
        dataset_path="outputs/test.jsonl",
        execution_target="modal",
    )
    assert cfg.execution_target == "modal"
    d = cfg.to_dict()
    assert d["execution_target"] == "modal"

    restored = FineTuneConfig.from_dict(d)
    assert restored.execution_target == "modal"


def test_trainer_modal_and_runpod_dispatch():
    events_modal = []
    cfg_modal = FineTuneConfig(
        dataset_path="outputs/test.jsonl",
        execution_target="modal",
    )
    trainer_modal = Trainer(cfg_modal)
    trainer_modal._train_modal(cfg_modal, [{"instruction": "q", "response": "a"}], events_modal.append, None)
    assert any(e.get("type") == "completed" for e in events_modal)

    events_runpod = []
    cfg_runpod = FineTuneConfig(
        dataset_path="outputs/test.jsonl",
        execution_target="runpod",
    )
    trainer_runpod = Trainer(cfg_runpod)
    trainer_runpod._train_runpod(cfg_runpod, [{"instruction": "q", "response": "a"}], events_runpod.append, None)
    assert any(e.get("type") == "completed" for e in events_runpod)
