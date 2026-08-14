"""
AI Platform Provider Implementations

HuggingFace Hub, Kaggle, GitHub Releases, DVC support.
"""

import asyncio
import io
import json
import os
import subprocess
from typing import Optional, AsyncIterator
from datetime import datetime

from core.storage.base import (
    StorageProvider,
    StorageConfig,
    StorageResult,
    StorageMetadata,
    StorageProviderType,
)


class HuggingFaceProvider(StorageProvider):
    """HuggingFace Hub storage provider."""

    provider_type = StorageProviderType.HUGGINGFACE

    async def initialize(self) -> None:
        """Initialize HuggingFace client."""
        try:
            from huggingface_hub import HfApi

            self._api = HfApi(
                token=self.config.credentials.get("token")
            )
            self._repo_id = self.config.metadata.get("repo_id", "")
        except ImportError:
            print("huggingface_hub not installed.")

    async def upload(
        self,
        data: bytes | AsyncIterator[bytes],
        destination: str,
        metadata: Optional[dict] = None
    ) -> StorageResult:
        """Upload to HuggingFace Hub."""
        start = datetime.utcnow()

        try:
            if self._api is None:
                await self.initialize()

            import tempfile

            # Write data to temp file
            with tempfile.NamedTemporaryFile(delete=False, suffix='.jsonl') as f:
                if hasattr(data, '__iter__') and not isinstance(data, bytes):
                    for chunk in data:
                        f.write(chunk)
                else:
                    f.write(data)
                temp_path = f.name

            # Upload to HF
            result = self._api.upload_file(
                path_or_fileobj=temp_path,
                path_in_repo=destination,
                repo_id=self._repo_id,
                repo_type="dataset"
            )

            os.unlink(temp_path)

            duration = (datetime.utcnow() - start).total_seconds() * 1000

            return StorageResult(
                success=True,
                location=str(result),
                duration_ms=duration,
            )

        except Exception as e:
            return StorageResult(success=False, location=destination, errors=[str(e)])

    async def upload_dataset(
        self,
        dataset_path: str,
        repo_id: str,
        private: bool = False
    ) -> StorageResult:
        """Upload a full dataset to HuggingFace."""
        start = datetime.utcnow()

        try:
            if self._api is None:
                await self.initialize()

            from huggingface_hub import create_repo

            # Create repo if needed
            try:
                create_repo(repo_id, repo_type="dataset", exist_ok=True, private=private)
            except Exception:
                pass

            # Upload directory
            self._api.upload_folder(
                folder_path=dataset_path,
                repo_id=repo_id,
                repo_type="dataset",
            )

            duration = (datetime.utcnow() - start).total_seconds() * 1000

            return StorageResult(
                success=True,
                location=f"https://huggingface.co/datasets/{repo_id}",
                duration_ms=duration,
            )

        except Exception as e:
            return StorageResult(success=False, location=repo_id, errors=[str(e)])

    async def download(self, source: str, destination_path: Optional[str] = None) -> StorageResult:
        """Download from HuggingFace Hub."""
        start = datetime.utcnow()

        try:
            from huggingface_hub import hf_hub_download

            # Parse source
            parts = source.replace("hf://", "").split("/")
            repo_id = "/".join(parts[:-1])
            filename = parts[-1]

            path = hf_hub_download(
                repo_id=repo_id,
                filename=filename,
                repo_type="dataset"
            )

            duration = (datetime.utcnow() - start).total_seconds() * 1000

            return StorageResult(
                success=True,
                location=path,
                duration_ms=duration,
            )

        except Exception as e:
            return StorageResult(success=False, location=source, errors=[str(e)])

    async def delete(self, path: str) -> bool:
        """Delete from HuggingFace."""
        try:
            if self._api is None:
                await self.initialize()

            parts = path.replace("hf://", "").split("/")
            repo_id = "/".join(parts[:-1])
            filename = parts[-1]

            self._api.delete_file(filename, repo_id=repo_id, repo_type="dataset")
            return True
        except Exception:
            return False

    async def exists(self, path: str) -> bool:
        """Check if file exists."""
        try:
            if self._api is None:
                await self.initialize()

            parts = path.replace("hf://", "").split("/")
            repo_id = "/".join(parts[:-1])
            filename = parts[-1]

            info = self._api.hf_hub_download(
                repo_id=repo_id,
                filename=filename,
                repo_type="dataset"
            )
            return info is not None
        except Exception:
            return False

    async def list_objects(self, prefix: str = "") -> list[str]:
        """List HuggingFace dataset files."""
        try:
            if self._api is None:
                await self.initialize()

            files = self._api.list_repo_files(
                repo_id=self._repo_id,
                repo_type="dataset"
            )

            if prefix:
                files = [f for f in files if f.startswith(prefix)]

            return [f"hf://{self._repo_id}/{f}" for f in files]
        except Exception:
            return []


class KaggleProvider(StorageProvider):
    """Kaggle dataset storage provider."""

    provider_type = StorageProviderType.KAGGLE

    async def initialize(self) -> None:
        """Initialize Kaggle client."""
        try:
            os.environ['KAGGLE_USERNAME'] = self.config.credentials.get("username", "")
            os.environ['KAGGLE_KEY'] = self.config.credentials.get("api_key", "")
        except Exception:
            pass

    async def upload_dataset(
        self,
        dataset_path: str,
        dataset_slug: str,
        public: bool = False
    ) -> StorageResult:
        """Upload dataset to Kaggle."""
        start = datetime.utcnow()

        try:
            from kaggle import api

            # Create dataset metadata
            metadata = {
                "title": dataset_slug.split('/')[-1],
                "id": dataset_slug,
                "licenses": [{"name": "CC0-1.0"}]
            }

            # Upload
            api.dataset_create_new(
                folder_path=dataset_path,
                public=public,
                convert_to_csv=False,
                dir_mode='zip'
            )

            duration = (datetime.utcnow() - start).total_seconds() * 1000

            return StorageResult(
                success=True,
                location=f"https://kaggle.com/datasets/{dataset_slug}",
                duration_ms=duration,
            )

        except Exception as e:
            return StorageResult(success=False, location=dataset_slug, errors=[str(e)])

    async def upload(
        self,
        data: bytes | AsyncIterator[bytes],
        destination: str,
        metadata: Optional[dict] = None
    ) -> StorageResult:
        """Upload to Kaggle (simplified)."""
        start = datetime.utcnow()

        try:
            if hasattr(data, '__iter__') and not isinstance(data, bytes):
                collected = b''.join(data)
            else:
                collected = data

            # Store locally for Kaggle upload
            import tempfile
            with tempfile.NamedTemporaryFile(delete=False, suffix='.jsonl') as f:
                f.write(collected)
                temp_path = f.name

            duration = (datetime.utcnow() - start).total_seconds() * 1000

            return StorageResult(
                success=True,
                location=temp_path,
                size_bytes=len(collected),
                duration_ms=duration,
            )

        except Exception as e:
            return StorageResult(success=False, location=destination, errors=[str(e)])

    async def download(self, source: str, destination_path: Optional[str] = None) -> StorageResult:
        """Download from Kaggle."""
        start = datetime.utcnow()

        try:
            from kaggle import api

            dataset_slug = source.replace("kaggle://", "")
            path = api.dataset_download_files(dataset_slug, path=destination_path, unzip=True)

            duration = (datetime.utcnow() - start).total_seconds() * 1000

            return StorageResult(
                success=True,
                location=destination_path or path,
                duration_ms=duration,
            )

        except Exception as e:
            return StorageResult(success=False, location=source, errors=[str(e)])


class GitHubReleasesProvider(StorageProvider):
    """GitHub Releases storage provider."""

    provider_type = StorageProviderType.GITHUB

    async def initialize(self) -> None:
        """Initialize GitHub client."""
        try:
            from github import Github

            self._client = Github(self.config.credentials.get("token"))
            self._repo = self.config.metadata.get("repo", "")
        except ImportError:
            print("PyGithub not installed.")

    async def upload_release(
        self,
        data: bytes,
        release_tag: str,
        filename: str,
        repo: Optional[str] = None
    ) -> StorageResult:
        """Upload asset to GitHub release."""
        start = datetime.utcnow()

        try:
            if self._client is None:
                await self.initialize()

            repo = repo or self._repo
            repository = self._client.get_repo(repo)

            # Get or create release
            try:
                release = repository.get_release(release_tag)
            except Exception:
                release = repository.create_git_release(release_tag, release_tag, "")

            # Upload asset
            import tempfile
            with tempfile.NamedTemporaryFile(delete=False) as f:
                f.write(data)
                temp_path = f.name

            asset = release.upload_asset(temp_path, name=filename)

            duration = (datetime.utcnow() - start).total_seconds() * 1000

            return StorageResult(
                success=True,
                location=asset.browser_download_url,
                size_bytes=len(data),
                duration_ms=duration,
            )

        except Exception as e:
            return StorageResult(success=False, location=release_tag, errors=[str(e)])

    async def upload(
        self,
        data: bytes | AsyncIterator[bytes],
        destination: str,
        metadata: Optional[dict] = None
    ) -> StorageResult:
        """Upload to GitHub releases."""
        return await self.upload_release(
            data=b''.join(data) if hasattr(data, '__iter__') and not isinstance(data, bytes) else data,
            release_tag=metadata.get("release_tag", "v1.0.0") if metadata else "v1.0.0",
            filename=destination.split('/')[-1]
        )

    async def download(self, source: str, destination_path: Optional[str] = None) -> StorageResult:
        """Download from GitHub release."""
        start = datetime.utcnow()

        try:
            # Parse source
            parts = source.replace("github://", "").split("/")
            repo = "/".join(parts[:2])
            release_tag = parts[2]
            filename = parts[3] if len(parts) > 3 else ""

            if self._client is None:
                await self.initialize()

            repository = self._client.get_repo(repo)
            release = repository.get_release(release_tag)

            for asset in release.get_assets():
                if asset.name == filename:
                    data = asset.download()
                    if destination_path:
                        with open(destination_path, 'wb') as f:
                            f.write(data)

                    duration = (datetime.utcnow() - start).total_seconds() * 1000

                    return StorageResult(
                        success=True,
                        location=destination_path or source,
                        size_bytes=asset.size,
                        duration_ms=duration,
                    )

            raise Exception(f"Asset {filename} not found")

        except Exception as e:
            return StorageResult(success=False, location=source, errors=[str(e)])


class DVCProvider(StorageProvider):
    """DVC (Data Version Control) storage provider."""

    provider_type = StorageProviderType.DVC

    async def initialize(self) -> None:
        """Initialize DVC."""
        self._remote = self.config.metadata.get("remote", "origin")

    async def push(
        self,
        dataset_path: str,
        remote: Optional[str] = None
    ) -> StorageResult:
        """Push dataset to DVC remote."""
        start = datetime.utcnow()

        try:
            remote = remote or self._remote

            # Add to DVC
            subprocess.run(['dvc', 'add', dataset_path], check=True, capture_output=True)

            # Push to remote
            subprocess.run(['dvc', 'push', '-r', remote], check=True, capture_output=True)

            duration = (datetime.utcnow() - start).total_seconds() * 1000

            return StorageResult(
                success=True,
                location=f"dvc://{remote}/{dataset_path}",
                duration_ms=duration,
            )

        except Exception as e:
            return StorageResult(success=False, location=dataset_path, errors=[str(e)])

    async def pull(
        self,
        dataset_path: str,
        remote: Optional[str] = None
    ) -> StorageResult:
        """Pull dataset from DVC remote."""
        start = datetime.utcnow()

        try:
            remote = remote or self._remote

            subprocess.run(['dvc', 'pull', '-r', remote, dataset_path], check=True, capture_output=True)

            duration = (datetime.utcnow() - start).total_seconds() * 1000

            return StorageResult(
                success=True,
                location=dataset_path,
                duration_ms=duration,
            )

        except Exception as e:
            return StorageResult(success=False, location=dataset_path, errors=[str(e)])

    async def upload(
        self,
        data: bytes | AsyncIterator[bytes],
        destination: str,
        metadata: Optional[dict] = None
    ) -> StorageResult:
        """Upload via DVC (simplified)."""
        import tempfile

        with tempfile.NamedTemporaryFile(delete=False, suffix='.jsonl') as f:
            if hasattr(data, '__iter__') and not isinstance(data, bytes):
                for chunk in data:
                    f.write(chunk)
            else:
                f.write(data)
            temp_path = f.name

        return await self.push(temp_path)

    async def download(self, source: str, destination_path: Optional[str] = None) -> StorageResult:
        """Download via DVC."""
        return await self.pull(source)