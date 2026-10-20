"""Hugging Face Hub Direct Publisher.

Uploads synthesized datasets, splits, and generated README.md Dataset Cards
directly to huggingface.co/datasets/{repo_id} using Hugging Face Hub REST API
or huggingface_hub client with zero external mandatory dependencies.
"""

import io
import json
import os
import urllib.request
import urllib.error
from typing import Any, Dict, List, Optional


def publish_dataset_to_hf_hub(
    repo_id: str,
    readme_content: str,
    samples: List[Dict[str, Any]],
    hf_token: Optional[str] = None,
    private: bool = False,
    split_name: str = "train",
) -> Dict[str, Any]:
    """
    Publish dataset files and README.md card directly to Hugging Face Hub.

    Args:
        repo_id: Target repository ID e.g. "username/indic-tax-instruct"
        readme_content: Generated markdown content for README.md dataset card
        samples: List of dataset sample dictionaries
        hf_token: Hugging Face User Access Token (with write permission). Defaults to env HF_TOKEN.
        private: Whether to create the repo as private.
        split_name: Dataset split name (default 'train').

    Returns:
        Dict containing success status, repo_url, and file status.
    """
    token = hf_token or os.environ.get("HF_TOKEN") or os.environ.get("HUGGINGFACE_HUB_TOKEN")
    if not token:
        raise ValueError(
            "Hugging Face Hub token is required. Provide 'hf_token' or set the 'HF_TOKEN' environment variable."
        )

    # Clean repo_id
    repo_id = repo_id.strip()
    if "/" not in repo_id:
        raise ValueError("Invalid repo_id format. Expected 'username/dataset-name' or 'org/dataset-name'.")

    # Try using huggingface_hub SDK if available
    try:
        from huggingface_hub import HfApi
        api = HfApi(token=token)
        # Create repository if it doesn't already exist
        api.create_repo(
            repo_id=repo_id,
            repo_type="dataset",
            private=private,
            exist_ok=True,
        )

        # Upload README.md
        api.upload_file(
            path_or_fileobj=readme_content.encode("utf-8"),
            path_in_repo="README.md",
            repo_id=repo_id,
            repo_type="dataset",
            commit_message="Add Hugging Face Dataset Card via RasoSynthTune",
        )

        # Upload JSONL split
        jsonl_data = "\n".join(json.dumps(s, ensure_ascii=False) for s in samples).encode("utf-8")
        api.upload_file(
            path_or_fileobj=jsonl_data,
            path_in_repo=f"data/{split_name}-00000-of-00001.jsonl",
            repo_id=repo_id,
            repo_type="dataset",
            commit_message=f"Upload {len(samples)} synthetic samples to {split_name} split",
        )

        repo_url = f"https://huggingface.co/datasets/{repo_id}"
        return {
            "success": True,
            "repo_id": repo_id,
            "repo_url": repo_url,
            "sample_count": len(samples),
            "files_uploaded": ["README.md", f"data/{split_name}-00000-of-00001.jsonl"],
            "method": "huggingface_hub_sdk",
        }

    except ImportError:
        # Fallback to direct Hugging Face REST API
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

        # 1. Create dataset repo
        create_url = "https://huggingface.co/api/repos/create"
        create_payload = json.dumps({
            "name": repo_id.split("/")[-1],
            "organization": repo_id.split("/")[0] if len(repo_id.split("/")) > 1 else None,
            "type": "dataset",
            "private": private,
        }).encode("utf-8")

        req = urllib.request.Request(create_url, data=create_payload, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req) as resp:
                pass
        except urllib.error.HTTPError as e:
            # 409 Conflict means repo already exists, which is acceptable
            if e.code != 409:
                err_body = e.read().decode("utf-8")
                raise RuntimeError(f"Hugging Face API repo creation failed ({e.code}): {err_body}")

        # 2. Upload README.md via commit API
        upload_url = f"https://huggingface.co/api/datasets/{repo_id}/commit/main"
        jsonl_str = "\n".join(json.dumps(s, ensure_ascii=False) for s in samples)

        commit_payload = {
            "summary": "Upload dataset and README via RasoSynthTune",
            "operations": [
                {
                    "operation": "add",
                    "path": "README.md",
                    "content": readme_content,
                    "encoding": "utf-8",
                },
                {
                    "operation": "add",
                    "path": f"data/{split_name}.jsonl",
                    "content": jsonl_str,
                    "encoding": "utf-8",
                }
            ]
        }

        commit_req = urllib.request.Request(
            upload_url,
            data=json.dumps(commit_payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        try:
            with urllib.request.urlopen(commit_req) as resp:
                pass
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8")
            raise RuntimeError(f"Hugging Face commit failed ({e.code}): {err_body}")

        repo_url = f"https://huggingface.co/datasets/{repo_id}"
        return {
            "success": True,
            "repo_id": repo_id,
            "repo_url": repo_url,
            "sample_count": len(samples),
            "files_uploaded": ["README.md", f"data/{split_name}.jsonl"],
            "method": "direct_rest_api",
        }
