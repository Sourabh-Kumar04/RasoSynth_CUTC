"""
Consumer Storage Provider Implementations

Google Drive, Dropbox, OneDrive, Mega support.
"""

import asyncio
import io
import hashlib
from typing import Optional, AsyncIterator
from datetime import datetime

from core.storage.base import (
    StorageProvider,
    StorageConfig,
    StorageResult,
    StorageMetadata,
    StorageProviderType,
)


class GoogleDriveProvider(StorageProvider):
    """Google Drive storage provider."""

    provider_type = StorageProviderType.GOOGLE_DRIVE

    async def initialize(self) -> None:
        """Initialize Google Drive client."""
        try:
            from google.oauth2.credentials import Credentials
            from googleapiclient.discovery import build

            credentials = Credentials(
                token=self.config.credentials.get("access_token"),
                refresh_token=self.config.credentials.get("refresh_token"),
                client_id=self.config.credentials.get("client_id"),
                client_secret=self.config.credentials.get("client_secret"),
                scopes=['https://www.googleapis.com/auth/drive.file']
            )

            self._service = build('drive', 'v3', credentials=credentials)
            self._folder_id = self.config.metadata.get("folder_id")
        except ImportError:
            print("google-api-python-client not installed.")

    async def upload(
        self,
        data: bytes | AsyncIterator[bytes],
        destination: str,
        metadata: Optional[dict] = None
    ) -> StorageResult:
        """Upload to Google Drive."""
        start = datetime.utcnow()

        try:
            if self._service is None:
                await self.initialize()

            # Collect streaming data
            if hasattr(data, '__iter__') and not isinstance(data, bytes):
                collected = b''.join(data)
                data = collected
            else:
                collected = data

            from googleapiclient.http import MediaIoBaseUpload

            file_metadata = {
                'name': destination.split('/')[-1],
                'parents': [self._folder_id] if self._folder_id else None,
            }

            fh = io.BytesIO(data)
            media = MediaIoBaseUpload(fh, mimetype='application/octet-stream')

            file = self._service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id, name, size'
            ).execute()

            duration = (datetime.utcnow() - start).total_seconds() * 1000

            return StorageResult(
                success=True,
                location=f"gdrive://{file.get('id')}",
                size_bytes=len(collected) if isinstance(collected, bytes) else 0,
                duration_ms=duration,
            )

        except Exception as e:
            return StorageResult(success=False, location=destination, errors=[str(e)])

    async def download(self, source: str, destination_path: Optional[str] = None) -> StorageResult:
        """Download from Google Drive."""
        start = datetime.utcnow()

        try:
            if self._service is None:
                await self.initialize()

            # Get file ID from source
            file_id = source.replace("gdrive://", "")

            response = self._service.files().get_media(fileId=file_id)

            fh = io.BytesIO()
            downloader = io.BytesIO(response.read())
            fh.write(downloader.read())
            fh.seek(0)

            data = fh.read()

            if destination_path:
                with open(destination_path, 'wb') as f:
                    f.write(data)

            duration = (datetime.utcnow() - start).total_seconds() * 1000

            return StorageResult(
                success=True,
                location=destination_path or source,
                size_bytes=len(data),
                duration_ms=duration,
            )

        except Exception as e:
            return StorageResult(success=False, location=source, errors=[str(e)])

    async def delete(self, path: str) -> bool:
        """Delete from Google Drive."""
        try:
            if self._service is None:
                await self.initialize()

            file_id = path.replace("gdrive://", "")
            self._service.files().delete(fileId=file_id).execute()
            return True
        except Exception:
            return False

    async def exists(self, path: str) -> bool:
        """Check if file exists."""
        try:
            if self._service is None:
                await self.initialize()

            file_id = path.replace("gdrive://", "")
            self._service.files().get(fileId=file_id, fields='id').execute()
            return True
        except Exception:
            return False

    async def list_objects(self, prefix: str = "") -> list[str]:
        """List Google Drive files."""
        try:
            if self._service is None:
                await self.initialize()

            query = f"name contains '{prefix}'" if prefix else ""
            results = self._service.files().list(
                q=query,
                spaces='drive',
                fields='files(id, name)'
            ).execute()

            return [f"gdrive://{f['id']}" for f in results.get('files', [])]
        except Exception:
            return []

    async def generate_signed_url(self, path: str, expiration_seconds: int = 3600) -> Optional[str]:
        """Generate shareable link."""
        try:
            if self._service is None:
                await self.initialize()

            file_id = path.replace("gdrive://", "")
            self._service.permissions().create(
                fileId=file_id,
                body={'type': 'anyone', 'role': 'reader'}
            ).execute()

            file = self._service.files().get(fileId=file_id, fields='webViewLink').execute()
            return file.get('webViewLink')
        except Exception:
            return None


class DropboxProvider(StorageProvider):
    """Dropbox storage provider."""

    provider_type = StorageProviderType.DROPBOX

    async def initialize(self) -> None:
        """Initialize Dropbox client."""
        try:
            import dropbox
            self._client = dropbox.Dropbox(self.config.credentials.get("access_token"))
        except ImportError:
            print("dropbox not installed.")

    async def upload(
        self,
        data: bytes | AsyncIterator[bytes],
        destination: str,
        metadata: Optional[dict] = None
    ) -> StorageResult:
        """Upload to Dropbox."""
        start = datetime.utcnow()

        try:
            if self._client is None:
                await self.initialize()

            # Collect streaming data
            if hasattr(data, '__iter__') and not isinstance(data, bytes):
                collected = b''.join(data)
            else:
                collected = data

            result = self._client.files_upload(
                collected,
                f"/{destination}",
                mode=dropbox.files.WriteMode.overwrite
            )

            duration = (datetime.utcnow() - start).total_seconds() * 1000

            return StorageResult(
                success=True,
                location=f"dropbox://{result.path_lower}",
                size_bytes=len(collected),
                duration_ms=duration,
            )

        except Exception as e:
            return StorageResult(success=False, location=destination, errors=[str(e)])

    async def download(self, source: str, destination_path: Optional[str] = None) -> StorageResult:
        """Download from Dropbox."""
        start = datetime.utcnow()

        try:
            if self._client is None:
                await self.initialize()

            path = source.replace("dropbox://", "")
            metadata, response = self._client.files_download(path)

            data = response.content

            if destination_path:
                with open(destination_path, 'wb') as f:
                    f.write(data)

            duration = (datetime.utcnow() - start).total_seconds() * 1000

            return StorageResult(
                success=True,
                location=destination_path or source,
                size_bytes=metadata.size,
                duration_ms=duration,
            )

        except Exception as e:
            return StorageResult(success=False, location=source, errors=[str(e)])

    async def delete(self, path: str) -> bool:
        """Delete from Dropbox."""
        try:
            if self._client is None:
                await self.initialize()

            self._client.files_delete_v2(path.replace("dropbox://", ""))
            return True
        except Exception:
            return False

    async def exists(self, path: str) -> bool:
        """Check if file exists."""
        try:
            if self._client is None:
                await self.initialize()

            self._client.files_get_metadata(path.replace("dropbox://", ""))
            return True
        except Exception:
            return False

    async def list_objects(self, prefix: str = "") -> list[str]:
        """List Dropbox files."""
        try:
            if self._client is None:
                await self.initialize()

            result = self._client.files_list_folder(prefix or "/")
            return [f"dropbox://{entry.path_lower}" for entry in result.entries]
        except Exception:
            return []

    async def generate_signed_url(self, path: str, expiration_seconds: int = 3600) -> Optional[str]:
        """Generate shareable link."""
        try:
            if self._client is None:
                await self.initialize()

            path = path.replace("dropbox://", "")
            result = self._client.files_get_temporary_link(path)
            return result.link
        except Exception:
            return None


class OneDriveProvider(StorageProvider):
    """Microsoft OneDrive storage provider."""

    provider_type = StorageProviderType.ONEDRIVE

    async def initialize(self) -> None:
        """Initialize OneDrive client."""
        try:
            from onedrive import OneDriveClient

            self._client = OneDriveClient(
                client_id=self.config.credentials.get("client_id"),
                client_secret=self.config.credentials.get("client_secret"),
                tenant_id=self.config.credentials.get("tenant_id", "common")
            )
            self._folder_id = self.config.metadata.get("folder_id", "root")
        except ImportError:
            print("onedrive-sdk-python not installed.")

    async def upload(
        self,
        data: bytes | AsyncIterator[bytes],
        destination: str,
        metadata: Optional[dict] = None
    ) -> StorageResult:
        """Upload to OneDrive."""
        start = datetime.utcnow()

        try:
            if self._client is None:
                await self.initialize()

            # Collect streaming data
            if hasattr(data, '__iter__') and not isinstance(data, bytes):
                collected = b''.join(data)
            else:
                collected = data

            path = f"/{self._folder_id}:/{destination.split('/')[-1]}:/content"

            result = self._client.put(path, collected)

            duration = (datetime.utcnow() - start).total_seconds() * 1000

            return StorageResult(
                success=True,
                location=f"onedrive://{result.id}",
                size_bytes=len(collected),
                duration_ms=duration,
            )

        except Exception as e:
            return StorageResult(success=False, location=destination, errors=[str(e)])

    async def download(self, source: str, destination_path: Optional[str] = None) -> StorageResult:
        """Download from OneDrive."""
        start = datetime.utcnow()

        try:
            if self._client is None:
                await self.initialize()

            item_id = source.replace("onedrive://", "")
            data = self._client.get(f"/{item_id}/content")

            if destination_path:
                with open(destination_path, 'wb') as f:
                    f.write(data)

            duration = (datetime.utcnow() - start).total_seconds() * 1000

            return StorageResult(
                success=True,
                location=destination_path or source,
                size_bytes=len(data),
                duration_ms=duration,
            )

        except Exception as e:
            return StorageResult(success=False, location=source, errors=[str(e)])

    async def delete(self, path: str) -> bool:
        """Delete from OneDrive."""
        try:
            if self._client is None:
                await self.initialize()

            item_id = path.replace("onedrive://", "")
            self._client.delete(f"/{item_id}")
            return True
        except Exception:
            return False

    async def exists(self, path: str) -> bool:
        """Check if file exists."""
        try:
            if self._client is None:
                await self.initialize()

            item_id = path.replace("onedrive://", "")
            self._client.get(f"/{item_id}")
            return True
        except Exception:
            return False

    async def list_objects(self, prefix: str = "") -> list[str]:
        """List OneDrive items."""
        try:
            if self._client is None:
                await self.initialize()

            path = f"/{self._folder_id}/children" if self._folder_id != "root" else "/root/children"
            result = self._client.get(path)
            return [f"onedrive://{item.id}" for item in result.get('value', [])]
        except Exception:
            return []


class MegaProvider(StorageProvider):
    """Mega.nz storage provider."""

    provider_type = StorageProviderType.MEGA

    async def initialize(self) -> None:
        """Initialize Mega client."""
        try:
            from mega import Mega

            mega = Mega()
            self._client = mega.login(
                email=self.config.credentials.get("email"),
                password=self.config.credentials.get("password")
            )
        except ImportError:
            print("mega.py not installed.")

    async def upload(
        self,
        data: bytes | AsyncIterator[bytes],
        destination: str,
        metadata: Optional[dict] = None
    ) -> StorageResult:
        """Upload to Mega."""
        start = datetime.utcnow()

        try:
            if self._client is None:
                await self.initialize()

            # Collect streaming data
            if hasattr(data, '__iter__') and not isinstance(data, bytes):
                collected = b''.join(data)
            else:
                collected = data

            import tempfile
            with tempfile.NamedTemporaryFile(delete=False) as f:
                f.write(collected)
                temp_path = f.name

            result = self._client.upload(temp_path, dest_path=destination)

            import os
            os.unlink(temp_path)

            duration = (datetime.utcnow() - start).total_seconds() * 1000

            return StorageResult(
                success=True,
                location=f"mega://{result}",
                size_bytes=len(collected),
                duration_ms=duration,
            )

        except Exception as e:
            return StorageResult(success=False, location=destination, errors=[str(e)])

    async def download(self, source: str, destination_path: Optional[str] = None) -> StorageResult:
        """Download from Mega."""
        start = datetime.utcnow()

        try:
            if self._client is None:
                await self.initialize()

            node_id = source.replace("mega://", "")
            data = self._client.download(node_id)

            if destination_path:
                with open(destination_path, 'wb') as f:
                    f.write(data)

            duration = (datetime.utcnow() - start).total_seconds() * 1000

            return StorageResult(
                success=True,
                location=destination_path or source,
                size_bytes=len(data),
                duration_ms=duration,
            )

        except Exception as e:
            return StorageResult(success=False, location=source, errors=[str(e)])

    async def delete(self, path: str) -> bool:
        """Delete from Mega."""
        try:
            if self._client is None:
                await self.initialize()

            node_id = path.replace("mega://", "")
            self._client.destroy(node_id)
            return True
        except Exception:
            return False

    async def exists(self, path: str) -> bool:
        """Check if file exists."""
        try:
            if self._client is None:
                await self.initialize()

            node_id = path.replace("mega://", "")
            self._client.get_node_by_id(node_id)
            return True
        except Exception:
            return False