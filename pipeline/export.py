"""Export pipeline with support for massive-scale and streaming."""
import json
import csv
import os
import shutil
import tempfile
from pathlib import Path
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import AsyncGenerator, Any, Dict, Iterator, Optional
import asyncio

# Optional S3 support
try:
    import boto3
    from botocore.exceptions import ClientError
    S3_AVAILABLE = True
except ImportError:
    S3_AVAILABLE = False
    boto3 = None
    ClientError = Exception


def _get_field(sample, field, default=""):
    """Get a field from a dict or object."""
    if isinstance(sample, dict):
        return sample.get(field, default)
    return getattr(sample, field, default)


@dataclass
class ExportConfig:
    """Configuration for dataset export with scale support."""
    format: str = "jsonl"
    output_dir: Path = Path("outputs")
    dataset_name: str = "dataset"
    include_metadata: bool = True
    compression: str | None = None
    streaming: bool = False
    batch_size: int = 1000
    quality_reports: bool = True
    # S3 settings
    s3_bucket: Optional[str] = None
    s3_region: Optional[str] = None
    # HuggingFace Hub settings
    hf_dataset_org: Optional[str] = None
    hf_token: Optional[str] = None
    # Kaggle settings
    kaggle_username: Optional[str] = None
    kaggle_key: Optional[str] = None


class StreamingExporter:
    """Exports samples in streaming fashion for large datasets."""

    def __init__(self, output_path: Path, format: str):
        self.output_path = output_path
        self.format = format
        self._file_handle = None

    def __enter__(self):
        self._file_handle = open(self.output_path, 'w', encoding='utf-8')
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._file_handle:
            self._file_handle.close()

    def write(self, sample: dict):
        """Write a single sample."""
        if self.format == "jsonl":
            self._file_handle.write(json.dumps(sample, ensure_ascii=False) + '\n')
        elif self.format == "csv":
            # Initialize CSV writer on first write
            if not hasattr(self, '_csv_writer') or self._csv_writer is None:
                fieldnames = list(sample.keys()) if isinstance(sample, dict) else sample.keys()
                self._csv_writer = csv.DictWriter(self._file_handle, fieldnames=fieldnames)
                self._csv_writer.writeheader()
            if isinstance(sample, dict):
                self._csv_writer.writerow(sample)
            elif hasattr(sample, '_asdict'):
                self._csv_writer.writerow(sample._asdict())

    def flush(self):
        """Flush buffer to disk."""
        self._file_handle.flush()


class ExportPipeline:
    """Enhanced export pipeline with streaming and large-scale support."""

    def __init__(self, config: ExportConfig):
        self.config = config
        self.output_dir = Path(config.output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._stats = {
            "total_exported": 0,
            "by_difficulty": {1: 0, 2: 0, 3: 0, 4: 0, 5: 0},
            "by_format": {},
        }

    async def export(
        self,
        samples: list,
        job_id: str,
        format: str | None = None
    ) -> dict[str, Path | str]:
        """Export samples in specified format(s)."""
        export_format = format or self.config.format

        # Create output directory for this job
        job_output_dir = self.output_dir / job_id
        job_output_dir.mkdir(parents=True, exist_ok=True)

        if export_format == "jsonl":
            output_path = await self._export_jsonl(samples, job_id, job_output_dir)
        elif export_format == "csv":
            output_path = await self._export_csv(samples, job_id, job_output_dir)
        elif export_format == "parquet":
            output_path = await self._export_parquet(samples, job_id, job_output_dir)
        elif export_format == "huggingface":
            output_path = await self._export_huggingface(samples, job_id, job_output_dir)
        elif export_format == "s3":
            output_path = await self._export_s3(samples, job_id, job_output_dir)
        elif export_format == "hf_hub":
            output_path = await self._export_huggingface_hub(samples, job_id, job_output_dir)
        elif export_format == "kaggle":
            output_path = await self._export_kaggle(samples, job_id, job_output_dir)
        else:
            output_path = await self._export_jsonl(samples, job_id, job_output_dir)

        # Generate reports
        reports = {}
        if self.config.quality_reports:
            reports = await self._generate_reports(samples, job_output_dir)

        return {"dataset": output_path, **reports}

    async def export_streaming(
        self,
        samples_iterator: Iterator,
        job_id: str,
        format: str | None = None
    ) -> Path:
        """Export samples in streaming fashion."""
        export_format = format or self.config.format
        output_path = self.output_dir / f"{job_id}.jsonl"

        with StreamingExporter(output_path, export_format) as exporter:
            for sample in samples_iterator:
                conversation = sample.get("conversation") if isinstance(sample, dict) else getattr(sample, "conversation", None)
                if conversation:
                    sample_dict = {
                        "conversation": conversation,
                        "metadata": sample.get("metadata") if isinstance(sample, dict) else sample.metadata,
                        "difficulty_tier": sample.get("difficulty_tier") if isinstance(sample, dict) else sample.difficulty_tier,
                        "curriculum_order": sample.get("curriculum_order") if isinstance(sample, dict) else sample.curriculum_order,
                    }
                else:
                    sample_dict = {
                        "instruction": sample.get("instruction") if isinstance(sample, dict) else sample.instruction,
                        "response": sample.get("response") if isinstance(sample, dict) else sample.response,
                        "input": sample.get("input") if isinstance(sample, dict) else sample.input,
                        "metadata": sample.get("metadata") if isinstance(sample, dict) else sample.metadata,
                        "difficulty_tier": sample.get("difficulty_tier") if isinstance(sample, dict) else sample.difficulty_tier,
                        "curriculum_order": sample.get("curriculum_order") if isinstance(sample, dict) else sample.curriculum_order,
                    }
                exporter.write(sample_dict)
                self._stats["total_exported"] += 1

                if hasattr(sample, 'difficulty_tier'):
                    tier = sample.difficulty_tier
                    self._stats["by_difficulty"][tier] = \
                        self._stats["by_difficulty"].get(tier, 0) + 1

        return output_path

    async def _export_jsonl(
        self,
        samples: list,
        job_id: str,
        output_dir: Path
    ) -> Path:
        """Export samples as JSON Lines."""
        output_path = output_dir / f"{job_id}.jsonl"

        with open(output_path, 'w', encoding='utf-8') as f:
            for sample in samples:
                record = self._sample_to_record(sample)
                f.write(json.dumps(record, ensure_ascii=False) + '\n')

        self._stats["total_exported"] += len(samples)
        self._update_difficulty_stats(samples)

        return output_path

    async def _export_csv(
        self,
        samples: list,
        job_id: str,
        output_dir: Path
    ) -> Path:
        """Export samples as CSV."""
        output_path = output_dir / f"{job_id}.csv"

        if not samples:
            return output_path

        # Get all possible fields (always include 'metadata' to avoid ValueError)
        fieldnames = set(["instruction", "response", "input", "difficulty_tier", "curriculum_order", "metadata"])
        for sample in samples:
            if hasattr(sample, 'metadata') and sample.metadata:
                fieldnames.update(sample.metadata.keys())

        with open(output_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=list(fieldnames))
            writer.writeheader()

            for sample in samples:
                row = self._sample_to_dict(sample)
                writer.writerow(row)

        return output_path

    async def _export_parquet(
        self,
        samples: list,
        job_id: str,
        output_dir: Path
    ) -> Path:
        """Export samples as Parquet."""
        output_path = output_dir / f"{job_id}.parquet"

        try:
            import pyarrow as pa
            import pyarrow.parquet as pq

            records = [self._sample_to_dict(s) for s in samples]

            sanitized_records = []
            for record in records:
                sanitized = {}
                for key, value in record.items():
                    if value is None:
                        sanitized[key] = ""
                    elif isinstance(value, (dict, list)):
                        sanitized[key] = json.dumps(value)
                    else:
                        sanitized[key] = str(value)
                sanitized_records.append(sanitized)

            table = pa.Table.from_pylist(sanitized_records)
            pq.write_table(table, output_path)
            return output_path
        except Exception:
            records = [self._sample_to_dict(s) for s in samples]
            with open(output_path, 'w', encoding='utf-8') as f:
                for record in records:
                    f.write(json.dumps(record, ensure_ascii=False) + '\n')
            return output_path

    async def _export_huggingface(
        self,
        samples: list,
        job_id: str,
        output_dir: Path
    ) -> Path:
        """Export samples in HuggingFace dataset format."""
        output_path = output_dir

        train, val, test = self._split_samples(samples, (0.8, 0.1, 0.1))

        for split_name, split_samples in [("train", train), ("validation", val), ("test", test)]:
            split_path = output_path / f"{split_name}.json"
            with open(split_path, 'w', encoding='utf-8') as f:
                json.dump([
                    self._sample_to_record(s) for s in split_samples
                ], f, ensure_ascii=False, indent=2)

        return output_path

    async def _export_s3(
        self,
        samples: list,
        job_id: str,
        output_dir: Path
    ) -> str:
        """Export samples to S3 by uploading the exported directory."""
        if not S3_AVAILABLE:
            raise RuntimeError("boto3 is not installed. Install boto3 to use S3 export.")

        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            # Export to temporary directory using a dedicated pipeline instance
            temp_config = ExportConfig(
                format=self.config.format,
                output_dir=tmpdir_path,
                dataset_name=self.config.dataset_name,
                include_metadata=self.config.include_metadata,
                compression=self.config.compression,
                streaming=self.config.streaming,
                batch_size=self.config.batch_size,
                quality_reports=self.config.quality_reports,
                s3_bucket=None,  # prevent recursion
                s3_region=self.config.s3_region
            )
            temp_exporter = ExportPipeline(temp_config)
            export_result = await temp_exporter.export(samples, "s3_export")
            # Upload all exported files to S3
            s3_client = boto3.client(
                's3',
                region_name=self.config.s3_region or os.getenv('AWS_DEFAULT_REGION', 'us-east-1'),
                aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
                aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY')
            )
            bucket = self.config.s3_bucket
            if not bucket:
                raise ValueError("S3 bucket not configured in ExportConfig.s3_bucket")
            # Walk the output directory and upload each file
            for root, _, files in os.walk(tmpdir_path):
                for file in files:
                    local_path = Path(root) / file
                    relative_path = local_path.relative_to(tmpdir_path)
                    s3_key = f"datasets/{job_id}/{relative_path.as_posix()}"
                    extra_args = {}
                    if file.endswith('.json'):
                        extra_args['ContentType'] = 'application/json'
                    elif file.endswith('.jsonl'):
                        extra_args['ContentType'] = 'application/jsonlines+json'
                    elif file.endswith('.csv'):
                        extra_args['ContentType'] = 'text/csv'
                    elif file.endswith('.parquet'):
                        extra_args['ContentType'] = 'application/octet-stream'
                    s3_client.upload_file(str(local_path), bucket, s3_key, ExtraArgs=extra_args)
            return f"s3://{bucket}/datasets/{job_id}/"

    async def _export_huggingface_hub(
        self,
        samples: list,
        job_id: str,
        output_dir: Path
    ) -> str:
        """Export samples to HuggingFace Hub."""
        try:
            from huggingface_hub import HfApi, create_repo
        except ImportError:
            raise RuntimeError("huggingface_hub is not installed.")

        if not self.config.hf_token:
            raise ValueError("HF token not configured. Set hf_token in ExportConfig.")

        api = HfApi(token=self.config.hf_token)
        dataset_name = f"{self.config.hf_dataset_org}/{self.config.dataset_name}-{job_id}" if self.config.hf_dataset_org else f"{self.config.dataset_name}-{job_id}"

        # Create or get existing repository
        try:
            create_repo(dataset_name, token=self.config.hf_token, repo_type="dataset", exist_ok=True)
        except Exception as e:
            raise RuntimeError(f"Failed to create HF repo: {e}")

        # Export locally first
        local_output = await self.export(samples, "jsonl")

        # Upload files
        for key, path in local_output.items():
            if isinstance(path, Path):
                if path.is_dir():
                    for root, _, files in os.walk(path):
                        for file in files:
                            local_path = Path(root) / file
                            relative_path = local_path.relative_to(path)
                            api.upload_file(
                                token=self.config.hf_token,
                                path_or_fileobj=str(local_path),
                                path_in_repo=relative_path.as_posix(),
                                repo_id=dataset_name,
                                repo_type="dataset"
                            )
                else:
                    api.upload_file(
                        token=self.config.hf_token,
                        path_or_fileobj=str(path),
                        path_in_repo=path.name,
                        repo_id=dataset_name,
                        repo_type="dataset"
                    )

        return f"https://huggingface.co/datasets/{dataset_name}"

    async def _export_kaggle(
        self,
        samples: list,
        job_id: str,
        output_dir: Path
    ) -> str:
        """Export samples to Kaggle."""
        if not self.config.kaggle_username or not self.config.kaggle_key:
            raise ValueError("Kaggle credentials not configured. Set kaggle_username and kaggle_key in ExportConfig.")

        # Export locally as CSV first
        local_output = await self._export_csv(samples, job_id, output_dir)

        # Create Kaggle dataset metadata
        dataset_metadata = {
            "title": self.config.dataset_name,
            "id": f"{self.config.kaggle_username}/{self.config.dataset_name}",
            "licenses": [{"name": "CC0-1.0"}]
        }

        # Write metadata
        meta_path = output_dir / "dataset-metadata.json"
        with open(meta_path, 'w') as f:
            json.dump(dataset_metadata, f, indent=2)

        return f"https://www.kaggle.com/datasets/{self.config.kaggle_username}/{self.config.dataset_name}"

    def _sample_to_record(self, sample) -> dict:
        """Convert sample to export record."""
        is_dict = isinstance(sample, dict)
        conversation = sample.get("conversation") if is_dict else getattr(sample, "conversation", None)
        if conversation:
            record = {
                "conversation": conversation
            }
        else:
            record = {
                "instruction": sample.get("instruction") if is_dict else sample.instruction,
                "response": sample.get("response") if is_dict else sample.response,
            }
            input_val = sample.get("input") if is_dict else sample.input
            if input_val:
                record["input"] = input_val

        if self.config.include_metadata:
            record["metadata"] = sample.get("metadata") if is_dict else sample.metadata
            record["difficulty_tier"] = sample.get("difficulty_tier") if is_dict else sample.difficulty_tier
            record["curriculum_order"] = sample.get("curriculum_order") if is_dict else sample.curriculum_order

        return record

    def _sample_to_dict(self, sample) -> dict:
        """Convert sample to dictionary."""
        is_dict = isinstance(sample, dict)
        record = {
            "instruction": sample.get("instruction") if is_dict else sample.instruction,
            "response": sample.get("response") if is_dict else sample.response,
            "input": (sample.get("input") if is_dict else sample.input) or "",
            "difficulty_tier": sample.get("difficulty_tier") if is_dict else sample.difficulty_tier,
            "curriculum_order": sample.get("curriculum_order") if is_dict else sample.curriculum_order,
            "metadata": json.dumps(sample.get("metadata") if is_dict else sample.metadata) if (sample.get("metadata") if is_dict else sample.metadata) else "{}",
        }
        conversation = sample.get("conversation") if is_dict else getattr(sample, "conversation", None)
        if conversation:
            record["conversation"] = json.dumps(conversation, ensure_ascii=False)
        return record

    def _split_samples(
        self,
        samples: list,
        ratios: tuple[float, float, float]
    ) -> tuple[list, list, list]:
        """Split samples into train/val/test."""
        total = len(samples)
        train_end = int(total * ratios[0])
        val_end = train_end + int(total * ratios[1])

        return samples[:train_end], samples[train_end:val_end], samples[val_end:]

    def _update_difficulty_stats(self, samples: list):
        """Update difficulty distribution statistics."""
        for sample in samples:
            if hasattr(sample, 'difficulty_tier'):
                tier = sample.difficulty_tier
                self._stats["by_difficulty"][tier] = \
                    self._stats["by_difficulty"].get(tier, 0) + 1

    async def generate_dataset_card(
        self,
        samples: list,
        output_dir: Path | None = None,
        job_metadata: dict | None = None
    ) -> Path:
        """Generate a comprehensive dataset card."""
        output_dir = output_dir or self.output_dir

        num_samples = len(samples)
        avg_instruction_len = sum(len(s.instruction) for s in samples) / max(num_samples, 1)
        avg_response_len = sum(len(s.response) for s in samples) / max(num_samples, 1)

        difficulty_dist = self._stats["by_difficulty"].copy()

        # Format distribution
        format_dist = {}
        for s in samples:
            fmt = getattr(s, 'format', 'alpaca')
            format_dist[fmt] = format_dist.get(fmt, 0) + 1

        # Quality distribution
        quality_dist = {"high": 0, "medium": 0, "low": 0}
        for s in samples:
            tier = getattr(s, 'difficulty_tier', 3)
            if tier >= 4:
                quality_dist["high"] += 1
            elif tier >= 2:
                quality_dist["medium"] += 1
            else:
                quality_dist["low"] += 1

        card = f"""# Dataset Card

## Overview
- **Dataset Name**: {self.config.dataset_name}
- **Generated**: {datetime.now(timezone.utc).isoformat()}
- **Total Samples**: {num_samples:,}
- **Format**: {self.config.format}
- **Export Stats**: {self._stats}

## Statistics
- **Average Instruction Length**: {avg_instruction_len:.1f} characters
- **Average Response Length**: {avg_response_len:.1f} characters
- **Difficulty Distribution**: {difficulty_dist}
- **Format Distribution**: {format_dist}
- **Quality Distribution**: {quality_dist}

## Sample Examples

### High Difficulty (Tier 4-5)
```
{samples[-1].instruction if samples else 'N/A'}
---
{samples[-1].response[:200] if samples else 'N/A'}...
```

### Medium Difficulty (Tier 2-3)
```
{samples[len(samples)//2].instruction if samples else 'N/A'}
---
{samples[len(samples)//2].response[:200] if samples else 'N/A'}...
```

### Low Difficulty (Tier 1)
```
{samples[0].instruction if samples else 'N/A'}
---
{samples[0].response[:200] if samples else 'N/A'}...
```

## Usage
```python
from datasets import load_dataset

dataset = load_dataset("{output_dir}")
train_dataset = dataset["train"]
```

## Quality Assurance
- Total samples passing filters: {sum(1 for s in samples if getattr(s, 'quality_score', 0) > 0.5)}
- Samples with warnings: {sum(1 for s in samples if getattr(s, 'warnings', []))}
- Unique content ratio: {len(set(_get_field(s, 'content', _get_field(s, 'response', '')) for s in samples)) / max(len(samples), 1):.2%}

## Maintenance
- Last updated: {datetime.now(timezone.utc).isoformat()}
- Version: 1.0

## License
MIT
"""

        if job_metadata:
            card += f"\n\n## Job Metadata\n```json\n{json.dumps(job_metadata, indent=2)}\n```\n"

        card_path = output_dir / "README.md"
        with open(card_path, 'w', encoding='utf-8') as f:
            f.write(card)

        return card_path

    async def generate_quality_report(
        self,
        samples: list,
        output_dir: Path | None = None
    ) -> dict:
        """Generate comprehensive quality metrics report."""
        output_dir = output_dir or self.output_dir

        quality_metrics = {
            "total_samples": len(samples),
            "avg_instruction_length": sum(len(s.instruction) for s in samples) / max(len(samples), 1),
            "avg_response_length": sum(len(s.response) for s in samples) / max(len(samples), 1),
            "difficulty_distribution": self._stats["by_difficulty"].copy(),
            "quality_indicators": {
                "high_quality": sum(1 for s in samples if getattr(s, 'difficulty_tier', 3) >= 4),
                "medium_quality": sum(1 for s in samples if 2 <= getattr(s, 'difficulty_tier', 3) < 4),
                "low_quality": sum(1 for s in samples if getattr(s, 'difficulty_tier', 3) < 2),
            },
            "metadata_fields": list(set(
                field
                for s in samples
                for field in (getattr(s, 'metadata', {}) or {}).keys()
            )),
        }

        # Calculate diversity metrics
        unique_instructions = len(set(s.instruction for s in samples))
        unique_responses = len(set(s.response for s in samples))

        quality_metrics["diversity"] = {
            "unique_instructions_ratio": unique_instructions / max(len(samples), 1),
            "unique_responses_ratio": unique_responses / max(len(samples), 1),
        }

        # Content length distribution
        lengths = [len(s.response) for s in samples]
        if lengths:
            import statistics
            quality_metrics["response_length_stats"] = {
                "mean": statistics.mean(lengths),
                "median": statistics.median(lengths),
                "stdev": statistics.stdev(lengths) if len(lengths) > 1 else 0,
                "min": min(lengths),
                "max": max(lengths),
            }

        report_path = output_dir / "quality_report.json"
        with open(report_path, 'w') as f:
            json.dump(quality_metrics, f, indent=2)

        return quality_metrics

    async def generate_lineage_report(
        self,
        samples: list,
        output_dir: Path | None = None
    ) -> dict:
        """Generate data lineage report."""
        output_dir = output_dir or self.output_dir

        sources = {}
        for sample in samples:
            metadata = getattr(sample, 'metadata', None) or getattr(sample, 'metadata_', None) or {}
            source = metadata.get("source_url", "unknown")
            sources[source] = sources.get(source, 0) + 1

        lineage = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "total_samples": len(samples),
            "sources": sources,
            "source_count": len(sources),
            "export_stats": self._stats,
        }

        report_path = output_dir / "lineage_report.json"
        with open(report_path, 'w') as f:
            json.dump(lineage, f, indent=2)

        return lineage

    async def generate_bias_report(
        self,
        samples: list,
        output_dir: Path | None = None
    ) -> dict:
        """Generate bias analysis report."""
        output_dir = output_dir or self.output_dir

        bias_analysis = {
            "sample_size": len(samples),
            "difficulty_balance": self._stats["by_difficulty"].copy(),
            "estimated_biases": [],
        }

        # Check difficulty balance
        total = sum(self._stats["by_difficulty"].values())
        if total > 0:
            for tier, count in self._stats["by_difficulty"].items():
                ratio = count / total
                if ratio > 0.5:
                    bias_analysis["estimated_biases"].append(
                        f"Heavy concentration in difficulty tier {tier} ({ratio:.1%})"
                    )
                elif ratio < 0.05:
                    bias_analysis["estimated_biases"].append(
                        f"Very few samples in difficulty tier {tier} ({ratio:.1%})"
                    )

        report_path = output_dir / "bias_report.json"
        with open(report_path, 'w') as f:
            json.dump(bias_analysis, f, indent=2)

        return bias_analysis

    async def _generate_reports(
        self,
        samples: list,
        output_dir: Path
    ) -> dict:
        """Generate all reports."""
        reports = {}

        quality_path = output_dir / "quality_report.json"
        quality_report = await self.generate_quality_report(samples, output_dir)
        reports["quality_report"] = str(quality_path)

        lineage_path = output_dir / "lineage_report.json"
        lineage_report = await self.generate_lineage_report(samples, output_dir)
        reports["lineage_report"] = str(lineage_path)

        bias_path = output_dir / "bias_report.json"
        bias_report = await self.generate_bias_report(samples, output_dir)
        reports["bias_report"] = str(bias_path)

        card_path = await self.generate_dataset_card(samples, output_dir)
        reports["dataset_card"] = str(card_path)

        return reports

    def get_stats(self) -> dict:
        """Get export statistics."""
        return self._stats.copy()