"""
RasoSynth Python SDK Client.

Provides high-level programmatic access to RasoSynth autonomous dataset synthesis,
cryptographic DBOM verification, and dataset exports.
"""
from __future__ import annotations

import os
import json
import time
import urllib.request
import urllib.error
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Union
from pathlib import Path


@dataclass
class DBOMAttestation:
    """Cryptographic Data Bill of Materials (DBOM) attestation container."""
    certificate_id: str = ""
    merkle_root: str = ""
    issued_at: str = ""
    domain: str = ""
    language: str = ""
    total_samples: int = 0
    raw: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DBOMAttestation":
        if not data:
            return cls()
        merkle = data.get("merkle_root_hash") or data.get("merkle_root", "")
        return cls(
            certificate_id=data.get("certificate_id", ""),
            merkle_root=merkle,
            issued_at=data.get("issued_at", ""),
            domain=data.get("domain", ""),
            language=data.get("language", ""),
            total_samples=data.get("total_samples", 0),
            raw=data,
        )


@dataclass
class JobResult:
    """Dataset synthesis job status and results representation."""
    job_id: str
    status: str
    progress: float = 0.0
    samples_generated: int = 0
    current_stage: str = ""
    error: Optional[str] = None
    dataset_id: Optional[str] = None
    export_path: Optional[str] = None
    dbom: DBOMAttestation = field(default_factory=DBOMAttestation)
    raw: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_completed(self) -> bool:
        return self.status.lower() in ("completed", "complete", "success")

    @property
    def is_failed(self) -> bool:
        return self.status.lower() in ("failed", "error")


class RasoSynthClient:
    """Client for RasoSynth dataset synthesis and verification."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: float = 60.0,
    ):
        self.api_key = api_key or os.environ.get("RASOSYNTH_API_KEY")
        if not self.api_key:
            raise ValueError(
                "Missing API key. Provide api_key argument or set RASOSYNTH_API_KEY environment variable."
            )
        self.base_url = (base_url or os.environ.get("RASOSYNTH_BASE_URL") or "http://localhost:8000").rstrip("/")
        self.timeout = timeout

    def _headers(self) -> Dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "RasoSynth-Python-SDK/2.0.0",
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def _request(self, method: str, path: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        url = f"{self.base_url}{path}"
        data = json.dumps(payload).encode("utf-8") if payload is not None else None
        req = urllib.request.Request(url, data=data, headers=self._headers(), method=method)
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                resp_data = resp.read().decode("utf-8")
                return json.loads(resp_data) if resp_data else {}
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8", errors="replace")
            try:
                err_json = json.loads(err_body)
                msg = err_json.get("detail", err_body)
            except Exception:
                msg = err_body
            raise RuntimeError(f"HTTP {e.code} error from RasoSynth API: {msg}") from e
        except urllib.error.URLError as e:
            raise ConnectionError(f"Could not connect to RasoSynth server at {url}: {e.reason}") from e

    def synthesize(
        self,
        domain: str,
        target_tokens: int = 500000,
        dataset_size: Optional[int] = None,
        quality_threshold: float = 0.85,
        export_format: str = "parquet",
        synthesis_mode: str = "standard",
        language: str = "en",
        wait: bool = True,
        poll_interval: float = 2.0,
        timeout: float = 300.0,
    ) -> JobResult:
        """Initiate dataset synthesis.

        Args:
            domain: Target topic, subject domain, or natural query.
            target_tokens: Target total tokens for dataset.
            dataset_size: Explicit number of sample pairs (defaults to ~ tokens / 350).
            quality_threshold: Neural score gate threshold [0.0 - 1.0].
            export_format: Export file format ('parquet', 'jsonl', 'huggingface', 'dpo').
            synthesis_mode: Engine mode ('standard', 'cot', 'socratic', 'tool_calling').
            language: Target language code ('en', 'hi', 'te', 'ta', etc.).
            wait: If True, blocks until job completes or fails.
            poll_interval: Seconds between status polls when wait=True.
            timeout: Maximum seconds to wait before raising TimeoutError.
        """
        # Calculate dataset_size from target_tokens if not explicitly supplied
        if dataset_size is None:
            dataset_size = max(5, int(target_tokens / 350))

        req_payload = {
            "target_domain": domain,
            "dataset_size": dataset_size,
            "export_format": export_format,
            "synthesis_mode": synthesis_mode,
            "language": language,
        }

        # Try API request
        resp = self._request("POST", "/jobs", req_payload)
        job_id = resp.get("job_id") or resp.get("id")
        if not job_id:
            raise RuntimeError(f"Unexpected response payload: {resp}")

        if not wait:
            return JobResult(
                job_id=job_id,
                status=resp.get("status", "pending"),
                current_stage=resp.get("current_stage", "pending"),
                raw=resp,
            )

        # Poll until completion
        start_time = time.time()
        while time.time() - start_time < timeout:
            result = self.get_job(job_id)
            if result.is_completed:
                return result
            if result.is_failed:
                raise RuntimeError(f"Job {job_id} failed: {result.error}")
            time.sleep(poll_interval)

        raise TimeoutError(f"Job {job_id} did not finish within {timeout} seconds.")

    def get_job(self, job_id: str) -> JobResult:
        """Fetch real-time job progression counters and DBOM attestation."""
        data = self._request("GET", f"/jobs/{job_id}")

        # Try to resolve DBOM if completed
        dbom_attestation = DBOMAttestation()
        try:
            dbom_data = self._request("GET", f"/datasets/{job_id}/dbom")
            if "dbom" in dbom_data:
                dbom_attestation = DBOMAttestation.from_dict(dbom_data["dbom"])
        except Exception:
            pass

        return JobResult(
            job_id=job_id,
            status=data.get("status", "unknown"),
            progress=data.get("progress", 0.0),
            samples_generated=data.get("samples_generated", 0),
            current_stage=data.get("current_stage", ""),
            error=data.get("error"),
            dbom=dbom_attestation,
            raw=data,
        )

    def _run_local_synthesis(self, req_payload: Dict[str, Any]) -> JobResult:
        """Run synthesis locally in-process without requiring a running web server."""
        import asyncio
        import uuid
        from datetime import datetime, timezone
        from core.orchestrator_core import DatasetOrchestrator
        from core.provider_router import ProviderRouter
        from core.storage.async_db import AsyncDB
        from orchestrator.job_manager import Job, JobStatus
        from core.export.dbom_attestor import generate_dbom_attestation

        job_id = str(uuid.uuid4())
        outputs_dir = os.path.abspath("outputs")
        os.makedirs(outputs_dir, exist_ok=True)

        async def _exec():
            db_path = os.path.join(outputs_dir, "local_sdk.db")
            db = await AsyncDB.create(f"sqlite+aiosqlite:///{db_path}")
            router = ProviderRouter()
            orchestrator = DatasetOrchestrator(
                {"output_dir": outputs_dir, "environment": "production"},
                router,
                db=db
            )
            job = Job(
                id=job_id,
                status=JobStatus.RUNNING,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
                current_stage="analyzing_constraints",
                progress=0.0,
                samples_processed=0,
                samples_generated=0,
                sources_discovered=0,
                sources_extracted=0,
                samples_filtered=0,
                cost_usd=0.0,
                error=None,
                config=req_payload,
            )
            await orchestrator.run(job)
            return job, db

        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    job_obj, db_inst = executor.submit(lambda: asyncio.run(_exec())).result()
            else:
                job_obj, db_inst = loop.run_until_complete(_exec())
        except RuntimeError:
            job_obj, db_inst = asyncio.run(_exec())

        # Resolve samples from DB for real DBOM attestation
        samples = []
        try:
            async def _fetch_samples():
                datasets = await db_inst.get_datasets_by_job(job_id)
                res = []
                for ds in datasets:
                    s_list = await db_inst.get_samples(ds["id"], limit=1000)
                    for s in s_list:
                        res.append({
                            "instruction": s.get("instruction", ""),
                            "response": s.get("response", ""),
                            "input": s.get("input", ""),
                        })
                return res

            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    import concurrent.futures
                    with concurrent.futures.ThreadPoolExecutor() as executor:
                        samples = executor.submit(lambda: asyncio.run(_fetch_samples())).result()
                else:
                    samples = loop.run_until_complete(_fetch_samples())
            except RuntimeError:
                samples = asyncio.run(_fetch_samples())
        except Exception:
            samples = []

        if not samples:
            raise RuntimeError(f"Local synthesis finished with no samples for job {job_id}.")

        real_dbom = generate_dbom_attestation(
            dataset_name=req_payload.get("target_domain", f"Dataset {job_id[:8]}"),
            samples=samples,
            domain=req_payload.get("target_domain", ""),
            language=req_payload.get("language", "en"),
            license_type="unknown",
            synthesis_mode=req_payload.get("synthesis_mode", "standard"),
        )

        dbom = DBOMAttestation(
            certificate_id=real_dbom["certificate_id"],
            merkle_root=real_dbom["merkle_root_hash"],
            domain=real_dbom.get("domain", ""),
            language=real_dbom.get("language", "en"),
            total_samples=real_dbom.get("total_samples", len(samples)),
        )

        return JobResult(
            job_id=job_id,
            status=job_obj.status.value if hasattr(job_obj.status, "value") else str(job_obj.status),
            progress=job_obj.progress,
            samples_generated=job_obj.samples_generated,
            current_stage=job_obj.current_stage,
            error=job_obj.error,
            dbom=dbom,
            raw={"id": job_id, "config": req_payload},
        )

    @staticmethod
    def verify_dbom(dataset_path: str, dbom_cert: Union[Dict[str, Any], str]) -> Dict[str, Any]:
        """Verify the cryptographic Merkle root of a dataset file against its DBOM certificate.

        Args:
            dataset_path: Path to .jsonl or .parquet dataset file.
            dbom_cert: DBOM certificate dict or path to .dbom.json file.
        """
        from core.export.dbom_attestor import verify_dataset_dbom

        # Load certificate
        if isinstance(dbom_cert, str):
            with open(dbom_cert, "r", encoding="utf-8") as f:
                cert = json.load(f)
        else:
            cert = dbom_cert

        # Load samples
        p = Path(dataset_path)
        samples = []
        if p.suffix == ".jsonl":
            with open(p, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        samples.append(json.loads(line))
        elif p.suffix == ".parquet":
            import pyarrow.parquet as pq
            table = pq.read_table(str(p))
            samples = table.to_pylist()
        else:
            raise ValueError(f"Unsupported dataset format for verification: {p.suffix}")

        return verify_dataset_dbom(samples, cert)
