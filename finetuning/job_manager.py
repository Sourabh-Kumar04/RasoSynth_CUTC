"""
Fine-tune job lifecycle manager.

Key improvements over v1:
- No thread-wrapping anti-pattern: Trainer.train() is a pure async generator,
  so we just `async for` over it directly.
- In-memory log ring buffer per job (capped at LOG_BUFFER_SIZE).
- `get_logs(job_id, limit)` for the /logs REST endpoint.
- `list_jobs` result cached for LIST_CACHE_TTL seconds to reduce DB load.
- Warns if MAX_CONCURRENT > 1 and CUDA is unavailable.
"""

from __future__ import annotations

import asyncio
import logging
import os
import uuid
from collections import deque
from datetime import datetime, timezone
from typing import AsyncGenerator, Optional

from core.db import DatabaseManager, FineTuneJob, utc_now
from finetuning.trainer import FineTuneConfig, Trainer

logger = logging.getLogger(__name__)

MAX_CONCURRENT_JOBS = int(os.environ.get("FINETUNE_MAX_CONCURRENT", "1"))
LOG_BUFFER_SIZE = int(os.environ.get("FINETUNE_LOG_BUFFER", "500"))
LIST_CACHE_TTL = 2.0  # seconds


def _cuda_available() -> bool:
    try:
        import torch
        return torch.cuda.is_available()
    except ImportError:
        return False


if MAX_CONCURRENT_JOBS > 1 and not _cuda_available():
    logger.warning(
        "FINETUNE_MAX_CONCURRENT=%d but CUDA is not available. "
        "Multiple concurrent fine-tune jobs will contend for CPU.",
        MAX_CONCURRENT_JOBS,
    )



def _is_valid_job_id(job_id: str) -> bool:
    """Job IDs are server-generated UUIDs. Anything else is rejected before
    the value is used as a filesystem path (log files) or a DB key, so a
    caller-supplied id can never traverse out of the log directory."""
    if not isinstance(job_id, str):
        return False
    try:
        return str(uuid.UUID(job_id)) == job_id.lower()
    except (ValueError, AttributeError, TypeError):
        return False


def _scrub_job_dict(job: Optional[dict]) -> Optional[dict]:
    """Strip secrets from a job dict before it leaves the manager.

    The HF token is needed in memory while training runs, but it must never
    be persisted in the job record nor returned by get_job/list_jobs (which
    would expose it to any authenticated API caller, including for rows
    written before this fix).
    """
    if not job:
        return job
    job = dict(job)
    config = job.get("config")
    if isinstance(config, dict) and "hf_token" in config:
        config = dict(config)
        config.pop("hf_token", None)
        job["config"] = config
    job.pop("hf_token", None)
    return job


def _webhook_allowed_and_safe(url: str) -> tuple[bool, str]:
    """Validate a webhook URL before dispatch.

    Returns (ok, reason). Checks, in order:
    - scheme is http/https only;
    - no embedded userinfo credentials;
    - optional WEBHOOK_ALLOWED_HOSTS allowlist (exact host or parent domain);
    - SSRF guard: the host must resolve, and every resolved address must be
      public (private/loopback/link-local/multicast/reserved/unspecified are
      rejected); DNS failure fails closed (no dispatch).
    NOTE: the DNS check happens before connect, so a rebinding TOCTOU window
    remains; it is accepted here because httpx connects by hostname. The
    guard still blocks the common SSRF cases (literal private IPs, localhost
    names, and metadata endpoints that resolve privately).
    """
    import ipaddress
    import socket
    from urllib.parse import urlparse

    try:
        parsed = urlparse(url)
    except Exception:
        return False, "unparsable URL"
    if parsed.scheme not in ("http", "https"):
        return False, f"disallowed scheme {parsed.scheme!r}"
    host = (parsed.hostname or "").lower()
    if not host:
        return False, "missing host"
    if parsed.username or parsed.password:
        return False, "userinfo credentials in webhook URL are not allowed"
    allowlist = [h.strip().lower() for h in os.getenv("WEBHOOK_ALLOWED_HOSTS", "").split(",") if h.strip()]
    if allowlist and not any(host == entry or host.endswith("." + entry) for entry in allowlist):
        return False, f"host {host} is not on WEBHOOK_ALLOWED_HOSTS"
    try:
        infos = socket.getaddrinfo(host, None)
    except Exception:
        return False, f"DNS resolution failed for {host}"
    if not infos:
        return False, f"DNS resolution returned nothing for {host}"
    for info in infos:
        try:
            ip = ipaddress.ip_address(info[4][0])
        except Exception:
            return False, "unparsable resolved address"
        if (ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast
                or ip.is_reserved or ip.is_unspecified):
            return False, f"host {host} resolves to non-public address {ip}"
    return True, ""


class FinetuneJobManager:
    """
    Singleton-style manager — one instance stored on app.state.ft_manager.
    """

    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager
        self._semaphore = asyncio.Semaphore(MAX_CONCURRENT_JOBS)
        # job_id -> asyncio.Task
        self._tasks: dict[str, asyncio.Task] = {}
        # job_id -> list[asyncio.Queue]  (one per WS subscriber)
        self._subscribers: dict[str, list[asyncio.Queue]] = {}
        # job_id -> deque[dict]  (capped ring buffer)
        self._logs: dict[str, deque] = {}
        # cached list result
        self._list_cache: Optional[list[dict]] = None
        self._list_cache_ts: float = 0.0

    # ── Public API ────────────────────────────────────────────────────────────

    async def create_job(self, config: dict) -> dict:
        job_id = str(uuid.uuid4())
        ft_config = FineTuneConfig.from_dict(config)
        ft_config.output_dir = str(os.path.join(ft_config.output_dir, job_id))

        # Pre-flight VRAM memory safety check
        if _cuda_available():
            try:
                import torch
                vram_gb = torch.cuda.get_device_properties(0).total_memory / (1024 ** 3)
                if vram_gb < 4.0 and ("7B" in ft_config.base_model.upper() or "8B" in ft_config.base_model.upper()):
                    logger.warning(
                        "Low VRAM detected (%.2f GB) for model %s. Forcing QLoRA 4-bit mode.",
                        vram_gb, ft_config.base_model
                    )
            except Exception as e:
                logger.debug("VRAM check skipped: %s", e)

        total_epochs = ft_config.num_train_epochs if ft_config.max_steps <= 0 else 1

        # Persist the config WITHOUT the HF token: the in-memory ft_config
        # keeps it for training, but the DB record must never hold it.
        persisted_config = ft_config.to_dict()
        persisted_config.pop("hf_token", None)
        fj = await self.db.create_finetune_job({
            "id": job_id,
            "status": "pending",
            "base_model": ft_config.base_model,
            "output_model_name": ft_config.output_model_name or job_id,
            "dataset_id": ft_config.dataset_id or None,
            "config": persisted_config,
            "total_epochs": total_epochs,
            "owner": config.get("owner"),
        })

        self._logs[job_id] = deque(maxlen=LOG_BUFFER_SIZE)
        self._list_cache = None  # Invalidate cache

        task = asyncio.create_task(self._run_job(job_id, ft_config), name=f"finetune-{job_id}")
        self._tasks[job_id] = task

        logger.info("Fine-tune job %s created (model=%s)", job_id, ft_config.base_model)
        return _scrub_job_dict(fj.to_dict())

    async def cancel_job(self, job_id: str) -> bool:
        if not _is_valid_job_id(job_id):
            logger.warning("Rejecting cancel for invalid job_id %r", job_id)
            return False
        task = self._tasks.get(job_id)
        if task and not task.done():
            task.cancel()
            await self.db.update_finetune_job(job_id, status="cancelled")
            await self._broadcast(job_id, {"type": "cancelled", "job_id": job_id})
            self._list_cache = None
            return True
        return False

    async def get_job(self, job_id: str) -> Optional[dict]:
        if not _is_valid_job_id(job_id):
            logger.warning("Rejecting get_job for invalid job_id %r", job_id)
            return None
        fj: Optional[FineTuneJob] = await self.db.get_finetune_job(job_id)
        return _scrub_job_dict(fj.to_dict()) if fj else None

    async def list_jobs(self, limit: int = 100, owner: Optional[str] = None) -> list[dict]:
        """Return jobs directly from DB to prevent cross-worker cache staleness in multi-process uvicorn."""
        jobs = await self.db.list_finetune_jobs(limit=limit, owner=owner)
        return [_scrub_job_dict(j.to_dict()) for j in jobs]

    def _persist_log_event(self, job_id: str, event: dict) -> None:
        """Persist event to shared container disk so all Uvicorn worker processes can read it."""
        try:
            log_dir = "/tmp/finetune_logs"
            os.makedirs(log_dir, exist_ok=True)
            log_file = os.path.join(log_dir, f"{job_id}.jsonl")
            import json
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(event) + "\n")
        except Exception:
            pass

    def get_logs(self, job_id: str, limit: int = 200) -> list[dict]:
        """Return last N log events from the in-memory ring buffer or shared worker disk cache."""
        if not _is_valid_job_id(job_id):
            logger.warning("Rejecting get_logs for invalid job_id %r", job_id)
            return []
        buf = self._logs.get(job_id)
        if buf and len(buf) > 0:
            entries = list(buf)
            return entries[-limit:] if limit < len(entries) else entries
        
        # Cross-worker fallback: read from shared disk
        try:
            log_file = os.path.join("/tmp/finetune_logs", f"{job_id}.jsonl")
            if os.path.exists(log_file):
                import json
                entries = []
                with open(log_file, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            entries.append(json.loads(line))
                self._logs[job_id] = deque(entries, maxlen=LOG_BUFFER_SIZE)
                return entries[-limit:] if limit < len(entries) else entries
        except Exception:
            pass
        return []

    async def subscribe(self, job_id: str) -> AsyncGenerator[dict, None]:
        """Async generator of training events for a job (WebSocket use)."""
        if not _is_valid_job_id(job_id):
            logger.warning("Rejecting subscribe for invalid job_id %r", job_id)
            return
        q: asyncio.Queue = asyncio.Queue(maxsize=512)
        self._subscribers.setdefault(job_id, []).append(q)
        try:
            current = await self.get_job(job_id)
            if current:
                yield {"type": "status", "job": current}
            # Replay buffered logs so late subscribers catch up
            for entry in self.get_logs(job_id):
                yield entry
            while True:
                try:
                    event = await asyncio.wait_for(q.get(), timeout=30.0)
                    yield event
                    if event.get("type") in ("completed", "error", "cancelled"):
                        break
                except asyncio.TimeoutError:
                    yield {"type": "ping"}
        finally:
            subs = self._subscribers.get(job_id, [])
            if q in subs:
                subs.remove(q)

    # ── Post-training evaluation ──────────────────────────────────────────────

    async def _run_post_training_eval(
        self,
        job_id: str,
        config: FineTuneConfig,
        event: dict,
    ) -> tuple[bool, Optional[str], Optional[dict]]:
        """Run automatic base-vs-fine-tuned comparative evaluation on held-out prompts.

        Executed after LoRA adapter export and BEFORE marking the job complete.
        Returns:
            (should_continue, error_message, eval_report)
        """
        from pathlib import Path
        import json
        from core.evaluation.held_out_split import NO_INTERNAL_EVAL_FLAG
        from core.evaluation.inference_harness import (
            evaluate_base_vs_finetuned,
            append_eval_to_model_card,
        )
        from core.export.huggingface_exporter import generate_hf_model_card

        out_path_str = event.get("output_path") or config.output_dir
        out_path = Path(out_path_str)
        out_path.mkdir(parents=True, exist_ok=True)

        # 1. Locate held-out split files
        val_candidates = []
        if config.dataset_path:
            ds_parent = Path(config.dataset_path).parent
            val_candidates.extend([
                ds_parent / "val.jsonl",
                ds_parent / "test.jsonl",
                ds_parent / "eval_held_out.jsonl",
            ])
        if config.dataset_id:
            val_candidates.extend([
                Path("outputs") / str(config.dataset_id) / "val.jsonl",
                Path("outputs") / str(config.dataset_id) / "test.jsonl",
            ])
        val_candidates.extend([
            out_path / "val.jsonl",
            out_path / "test.jsonl",
            Path(config.output_dir) / "val.jsonl",
        ])

        held_out_samples = []
        source_val_file = None
        for cand in val_candidates:
            if cand.exists() and cand.is_file():
                source_val_file = cand
                try:
                    with open(cand, "r", encoding="utf-8") as f:
                        for line in f:
                            line = line.strip()
                            if line:
                                held_out_samples.append(json.loads(line))
                    if held_out_samples:
                        break
                except Exception as e:
                    logger.debug("Failed reading val split %s: %s", cand, e)

        # 2. Check for split_manifest.json (holdout decision)
        holdout_decision = None
        manifest_candidates = [
            out_path / "split_manifest.json",
        ]
        if config.dataset_path:
            manifest_candidates.append(Path(config.dataset_path).parent / "split_manifest.json")
        for mc in manifest_candidates:
            if mc.exists():
                try:
                    with open(mc, "r", encoding="utf-8") as f:
                        holdout_decision = json.load(f)
                    break
                except Exception:
                    pass

        # If sample count was below floor or no held-out samples carved
        if not held_out_samples and not holdout_decision:
            # Query dataset size
            sample_count = 0
            if hasattr(self, "db") and self.db and config.dataset_id:
                try:
                    ds = await self.db.get_dataset(str(config.dataset_id))
                    if ds:
                        sample_count = getattr(ds, "size", 0) or 0
                except Exception:
                    pass
            holdout_decision = {
                "floor": 1000,
                "total_samples": sample_count,
                "train_count": sample_count,
                "val_count": 0,
                "test_count": 0,
                "status": "below_floor_100_pct_train" if sample_count < 1000 else "no_split_found",
                "flag": NO_INTERNAL_EVAL_FLAG if sample_count < 1000 else None,
            }

        # 3. Execute evaluation comparison
        policy = os.getenv("EVAL_REGRESSION_POLICY", "warn").strip().lower()
        eval_report = evaluate_base_vs_finetuned(
            base_model_id=config.base_model,
            adapter_path=str(out_path),
            held_out_samples=held_out_samples,
            job_id=job_id,
            chat_template=config.chat_template,
            regression_policy=policy,
        )

        # 4. Check regression policy block vs warn
        if eval_report.get("blocks_completion"):
            err_msg = (
                f"Evaluation regression blocked job completion: fine-tuned adapter showed negative delta vs base "
                f"(composite delta: {eval_report.get('headline_composite_delta')}, win rate: {eval_report.get('win_rate_pct')}%). "
                f"Failing job per regression policy='block'."
            )
            logger.error("[%s] %s", job_id, err_msg)
            return False, err_msg, eval_report

        # 5. Persist eval_report.json artifact
        try:
            with open(out_path / "eval_report.json", "w", encoding="utf-8") as f:
                json.dump(eval_report, f, indent=2)
        except Exception as e:
            logger.warning("[%s] Failed saving eval_report.json: %s", job_id, e)

        # 6. Append to Hugging Face Model Card (README.md)
        readme_path = out_path / "README.md"
        current_readme = ""
        if readme_path.exists():
            try:
                current_readme = readme_path.read_text(encoding="utf-8")
            except Exception:
                current_readme = ""
        if not current_readme:
            current_readme = generate_hf_model_card(
                model_name=config.output_model_name or job_id,
                base_model=config.base_model,
                dataset_name=config.dataset_id or "dataset",
                sample_count=holdout_decision.get("total_samples") if holdout_decision else None,
                epochs=config.num_train_epochs,
                learning_rate=config.learning_rate,
                lora_r=config.lora_r,
                lora_alpha=config.lora_alpha,
                holdout_decision=holdout_decision,
            )

        updated_readme = append_eval_to_model_card(current_readme, eval_report, holdout_decision)
        try:
            readme_path.write_text(updated_readme, encoding="utf-8")
        except Exception as e:
            logger.warning("[%s] Failed writing evaluation to model card README.md: %s", job_id, e)

        return True, None, eval_report

    # ── Internal ──────────────────────────────────────────────────────────────

    async def _run_job(self, job_id: str, config: FineTuneConfig):
        async with self._semaphore:
            await self.db.update_finetune_job(job_id, status="running", started_at=utc_now())
            self._list_cache = None
            start_event = {"type": "started", "job_id": job_id, "timestamp": datetime.now(timezone.utc).isoformat()}
            self._persist_log_event(job_id, start_event)
            await self._broadcast(job_id, start_event)

            trainer = Trainer(config)
            persisted_config = config.to_dict()
            persisted_config.pop("hf_token", None)
            simulated_job = bool(persisted_config.get("is_simulated", False))
            try:
                async for event in trainer.train():
                    event["job_id"] = job_id

                    # Store in ring buffer and persist to shared disk across worker processes
                    buf = self._logs.setdefault(job_id, deque(maxlen=LOG_BUFFER_SIZE))
                    buf.append(event)
                    self._persist_log_event(job_id, event)

                    await self._broadcast(job_id, event)
                    etype = event.get("type")

                    if event.get("is_simulated"):
                        simulated_job = True
                        persisted_config["is_simulated"] = True
                        await self.db.update_finetune_job(job_id, is_simulated=True, config=persisted_config)

                    if etype == "progress":
                        await self.db.update_finetune_job(
                            job_id,
                            progress=event.get("progress", 0),
                            current_epoch=int(event.get("epoch", 0)),
                            train_loss=event.get("loss"),
                            is_simulated=simulated_job,
                        )
                    elif etype == "eval":
                        await self.db.update_finetune_job(job_id, eval_loss=event.get("eval_loss"))
                    elif etype == "completed":
                        # Post-training evaluation on held-out prompts BEFORE marking complete
                        should_continue, err_msg, eval_report = await self._run_post_training_eval(
                            job_id, config, event
                        )
                        if not should_continue:
                            # Regression blocked completion per policy
                            await self.db.update_finetune_job(
                                job_id,
                                status="failed",
                                error=err_msg,
                                completed_at=utc_now(),
                            )
                            self._list_cache = None
                            error_event = {
                                "type": "error",
                                "job_id": job_id,
                                "message": err_msg,
                                "eval_report": eval_report,
                            }
                            self._persist_log_event(job_id, error_event)
                            await self._broadcast(job_id, error_event)
                            await self._dispatch_webhook(config.webhook_url, job_id, "failed", error_event, config)
                            break

                        if eval_report:
                            persisted_config["eval_report"] = eval_report
                            event["eval_report"] = eval_report

                        await self.db.update_finetune_job(
                            job_id, status="completed", progress=100.0,
                            output_path=event.get("output_path"),
                            hf_repo_url=event.get("hf_repo_url"),
                            completed_at=utc_now(),
                            is_simulated=simulated_job,
                            config=persisted_config,
                        )
                        self._list_cache = None
                        logger.info("Fine-tune job %s completed", job_id)
                        await self._dispatch_webhook(config.webhook_url, job_id, "completed", event, config)
                    elif etype == "error":
                        await self.db.update_finetune_job(
                            job_id, status="failed",
                            error=event.get("message"),
                            completed_at=utc_now(),
                        )
                        self._list_cache = None
                        logger.error("Fine-tune job %s failed: %s", job_id, event.get("message"))
                        await self._dispatch_webhook(config.webhook_url, job_id, "failed", event, config)
                    elif etype == "cancelled":
                        await self.db.update_finetune_job(
                            job_id, status="cancelled", completed_at=datetime.now(timezone.utc)
                        )
                        self._list_cache = None
                        await self._dispatch_webhook(config.webhook_url, job_id, "cancelled", event, config)

            except asyncio.CancelledError:
                trainer.cancel()
                await self.db.update_finetune_job(
                    job_id, status="cancelled", completed_at=datetime.now(timezone.utc)
                )
                await self._broadcast(job_id, {"type": "cancelled", "job_id": job_id})
                self._list_cache = None
                await self._dispatch_webhook(config.webhook_url, job_id, "cancelled", {"message": "Job cancelled"}, config)

            except Exception as exc:
                await self.db.update_finetune_job(
                    job_id, status="failed", error=str(exc), completed_at=datetime.now(timezone.utc)
                )
                await self._broadcast(job_id, {"type": "error", "job_id": job_id, "message": str(exc)})
                self._list_cache = None
                logger.exception("Unexpected error in fine-tune job %s", job_id)
                await self._dispatch_webhook(config.webhook_url, job_id, "failed", {"message": str(exc)}, config)

            finally:
                self._tasks.pop(job_id, None)

    async def _dispatch_webhook(
        self,
        webhook_url: Optional[str],
        job_id: str,
        status: str,
        event: dict,
        config: FineTuneConfig,
    ):
        if not webhook_url or not str(webhook_url).strip():
            return

        url = str(webhook_url).strip()
        ok, reason = _webhook_allowed_and_safe(url)
        if not ok:
            logger.warning("Skipping webhook dispatch for job %s: %s", job_id, reason)
            return
        base_model = config.base_model
        output_name = config.output_model_name or job_id
        target = config.execution_target
        loss = event.get("loss") or event.get("train_loss") or "N/A"
        err_msg = event.get("message") or event.get("error") or ""

        title = f"RasoSynthTune Fine-Tuning Job {status.upper()}"
        summary = (
            f"Job ID: `{job_id}`\n"
            f"Base Model: `{base_model}`\n"
            f"Hardware Engine: `{target}`\n"
            f"Status: **{status}**"
        )
        is_simulated_run = bool(event.get("is_simulated") or getattr(config, "is_simulated", False) or getattr(config, "execution_target", "") in ("modal", "colab", "runpod", "serverless") and event.get("is_simulated"))
        if is_simulated_run:
            logger.info("Finetune job %s is simulated; omitting loss/artifact claims from webhook notification.", job_id)
            title = f"RasoSynthTune Fine-Tuning Job {status.upper()} (SIMULATED)"
            summary = (
                f"Job ID: `{job_id}`\n"
                f"Base Model: `{base_model}`\n"
                f"Hardware Engine: `{target}` (Simulated Run)\n"
                f"Status: **{status} (Simulated)**\n"
                f"Note: This was a simulated/stub execution. No real model artifacts or loss metrics were produced."
            )
            loss = "N/A (Simulated)"
        elif status == "completed":
            summary += f"\nFinal Loss: `{loss}`\nArtifacts ready for download."
        elif err_msg:
            summary += f"\nError: `{err_msg}`"

        payload = {
            "event": f"finetune_job_{status}",
            "job_id": job_id,
            "status": status,
            "base_model": base_model,
            "output_model_name": output_name,
            "execution_target": target,
            "loss": str(loss),
            "error": err_msg,
            "download_url": f"/api/finetune/jobs/{job_id}/download",
            "gguf_url": f"/api/finetune/jobs/{job_id}/export-gguf",
            "text": summary,
            "content": summary,
            "embeds": [
                {
                    "title": title,
                    "description": summary,
                    "color": 0x22c55e if status == "completed" else 0xef4444,
                }
            ],
        }

        try:
            import hashlib
            import hmac
            import httpx
            import json as _json
            from urllib.parse import urlparse as _urlparse
            headers = {}
            signing_secret = os.getenv("WEBHOOK_SIGNING_SECRET", "")
            if signing_secret:
                digest = hmac.new(
                    signing_secret.encode(),
                    _json.dumps(payload, sort_keys=True, default=str).encode(),
                    hashlib.sha256,
                ).hexdigest()
                headers["X-RasoSynth-Signature"] = f"sha256={digest}"
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(url, json=payload, headers=headers)
                # Log the host only, never the full URL (it may carry query secrets).
                logger.info(
                    "Dispatched webhook for job %s to %s (status %s, signed=%s)",
                    job_id, _urlparse(url).hostname, resp.status_code, bool(headers),
                )
        except Exception as e:
            from urllib.parse import urlparse as _urlparse2
            logger.warning("Failed to dispatch webhook for job %s to %s: %s", job_id, _urlparse2(url).hostname, e)

    async def _broadcast(self, job_id: str, event: dict):
        for q in list(self._subscribers.get(job_id, [])):
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                pass
