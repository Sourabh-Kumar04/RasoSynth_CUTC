"""
Cloud Storage Provider Implementations

Supports multiple cloud storage backends with unified interface.
"""

import asyncio
import os
import io
import hashlib
import mimetypes
from typing import Optional, AsyncIterator
from datetime import datetime

from core.storage.base import (
    StorageProvider,
    StorageConfig,
    StorageResult,
    StorageMetadata,
    StorageProviderType,
    DeliveryStrategy,
    ProgressTracker,
)
from core.storage.packaging import DatasetPackager, PackageManifest


class S3StorageProvider(StorageProvider):
    """Amazon S3 storage provider."""

    provider_type = StorageProviderType.AWS_S3

    def __init__(self, config: StorageConfig):
        super().__init__(config)
        self._client = None
        self._s3 = None

    async def initialize(self) -> None:
        """Initialize S3 client."""
        try:
            import boto3
            self._s3 = boto3.Session(
                aws_access_key_id=self.config.credentials.get("access_key"),
                aws_secret_access_key=self.config.credentials.get("secret_key"),
                region_name=self.config.region,
            ).client('s3')

            self._client = self._s3
        except ImportError:
            print("boto3 not installed. S3 operations unavailable.")

    async def upload(
        self,
        data: bytes | AsyncIterator[bytes],
        destination: str,
        metadata: Optional[dict] = None
    ) -> StorageResult:
        """Upload to S3."""
        start = datetime.utcnow()

        try:
            if self._client is None:
                await self.initialize()

            # Handle streaming data
            if hasattr(data, '__iter__'):
                body = io.BytesIO(b''.join(data))
            else:
                body = data

            extra_args = {
                'ContentType': metadata.get('content_type', 'application/octet-stream'),
                'Metadata': metadata or {},
            }

            if self.config.encryption:
                extra_args['ServerSideEncryption'] = self.config.encryption

            self._client.put_object(
                Bucket=self.config.bucket,
                Key=destination,
                Body=body,
                **extra_args
            )

            duration = (datetime.utcnow() - start).total_seconds() * 1000

            return StorageResult(
                success=True,
                location=f"s3://{self.config.bucket}/{destination}",
                size_bytes=len(data) if isinstance(data, bytes) else 0,
                duration_ms=duration,
            )

        except Exception as e:
            return StorageResult(
                success=False,
                location=destination,
                errors=[str(e)]
            )

    async def download(self, source: str, destination_path: Optional[str] = None) -> StorageResult:
        """Download from S3."""
        start = datetime.utcnow()

        try:
            if self._client is None:
                await self.initialize()

            response = self._client.get_object(
                Bucket=self.config.bucket,
                Key=source
            )

            data = response['Body'].read()

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
        """Delete from S3."""
        try:
            if self._client is None:
                await self.initialize()

            self._client.delete_object(Bucket=self.config.bucket, Key=path)
            return True
        except Exception:
            return False

    async def exists(self, path: str) -> bool:
        """Check if object exists."""
        try:
            if self._client is None:
                await self.initialize()

            self._client.head_object(Bucket=self.config.bucket, Key=path)
            return True
        except Exception:
            return False

    async def get_metadata(self, path: str) -> Optional[StorageMetadata]:
        """Get S3 object metadata."""
        try:
            if self._client is None:
                await self.initialize()

            response = self._client.head_object(Bucket=self.config.bucket, Key=path)

            return StorageMetadata(
                key=path,
                size_bytes=response['ContentLength'],
                content_type=response.get('ContentType', 'application/octet-stream'),
                created_at=response.get('LastModified', datetime.utcnow()),
                modified_at=response.get('LastModified', datetime.utcnow()),
                checksum=response.get('ETag', '').strip('"'),
                storage_class=response.get('StorageClass', 'STANDARD'),
                region=self.config.region,
                bucket=self.config.bucket,
            )
        except Exception:
            return None

    async def list_objects(self, prefix: str = "") -> list[str]:
        """List S3 objects."""
        try:
            if self._client is None:
                await self.initialize()

            response = self._client.list_objects_v2(
                Bucket=self.config.bucket,
                Prefix=prefix
            )

            return [obj['Key'] for obj in response.get('Contents', [])]
        except Exception:
            return []

    async def generate_signed_url(self, path: str, expiration_seconds: int = 3600) -> Optional[str]:
        """Generate signed URL."""
        try:
            if self._client is None:
                await self.initialize()

            return self._client.generate_presigned_url(
                'get_object',
                Params={'Bucket': self.config.bucket, 'Key': path},
                ExpiresIn=expiration_seconds
            )
        except Exception:
            return None

    async def multipart_upload(
        self,
        file_path: str,
        destination: str,
        progress_callback: Optional[callable] = None
    ) -> StorageResult:
        """Multipart upload for large files."""
        start = datetime.utcnow()

        try:
            if self._client is None:
                await self.initialize()

            file_size = os.path.getsize(file_path)
            chunk_size = self.config.multipart_chunk_mb * 1024 * 1024

            # Start multipart upload
            mpu = self._client.create_multipart_upload(
                Bucket=self.config.bucket,
                Key=destination,
                StorageClass=self.config.storage_class,
            )

            upload_id = mpu['UploadId']
            parts = []
            uploaded_bytes = 0

            with open(file_path, 'rb') as f:
                part_number = 1
                while True:
                    chunk = f.read(chunk_size)
                    if not chunk:
                        break

                    # Upload part
                    part = self._client.upload_part(
                        Bucket=self.config.bucket,
                        Key=destination,
                        UploadId=upload_id,
                        PartNumber=part_number,
                        Body=chunk,
                    )

                    parts.append({'PartNumber': part_number, 'ETag': part['ETag']})
                    uploaded_bytes += len(chunk)
                    part_number += 1

                    if progress_callback:
                        progress_callback(uploaded_bytes, file_size)

            # Complete multipart upload
            self._client.complete_multipart_upload(
                Bucket=self.config.bucket,
                Key=destination,
                UploadId=upload_id,
                MultipartUpload={'Parts': parts}
            )

            duration = (datetime.utcnow() - start).total_seconds() * 1000

            return StorageResult(
                success=True,
                location=f"s3://{self.config.bucket}/{destination}",
                size_bytes=file_size,
                duration_ms=duration,
                parts_completed=len(parts),
                total_parts=len(parts),
            )

        except Exception as e:
            return StorageResult(success=False, location=destination, errors=[str(e)])


class GCSStorageProvider(StorageProvider):
    """Google Cloud Storage provider."""

    provider_type = StorageProviderType.GOOGLE_GCS

    async def initialize(self) -> None:
        """Initialize GCS client."""
        try:
            from google.cloud import storage
            self._client = storage.Client.from_service_account_json(
                self.config.credentials.get("credentials_file")
            )
            self._bucket = self._client.bucket(self.config.bucket)
        except ImportError:
            print("google-cloud-storage not installed.")

    async def upload(
        self,
        data: bytes | AsyncIterator[bytes],
        destination: str,
        metadata: Optional[dict] = None
    ) -> StorageResult:
        """Upload to GCS."""
        start = datetime.utcnow()

        try:
            if self._client is None:
                await self.initialize()

            blob = self._bucket.blob(destination)

            if hasattr(data, '__iter__') and not isinstance(data, bytes):
                blob.upload_from_file(data)
            else:
                blob.upload_from_string(data)

            duration = (datetime.utcnow() - start).total_seconds() * 1000

            return StorageResult(
                success=True,
                location=f"gs://{self.config.bucket}/{destination}",
                size_bytes=len(data) if isinstance(data, bytes) else 0,
                duration_ms=duration,
            )

        except Exception as e:
            return StorageResult(success=False, location=destination, errors=[str(e)])

    async def download(self, source: str, destination_path: Optional[str] = None) -> StorageResult:
        """Download from GCS."""
        start = datetime.utcnow()

        try:
            if self._client is None:
                await self.initialize()

            blob = self._bucket.blob(source)

            if destination_path:
                blob.download_to_filename(destination_path)
            else:
                data = blob.download_as_bytes()

            duration = (datetime.utcnow() - start).total_seconds() * 1000

            return StorageResult(
                success=True,
                location=destination_path or source,
                size_bytes=blob.size or 0,
                duration_ms=duration,
            )

        except Exception as e:
            return StorageResult(success=False, location=source, errors=[str(e)])

    async def delete(self, path: str) -> bool:
        """Delete from GCS."""
        try:
            if self._client is None:
                await self.initialize()

            self._bucket.blob(path).delete()
            return True
        except Exception:
            return False

    async def exists(self, path: str) -> bool:
        """Check if object exists."""
        try:
            if self._client is None:
                await self.initialize()

            return self._bucket.blob(path).exists()
        except Exception:
            return False

    async def get_metadata(self, path: str) -> Optional[StorageMetadata]:
        """Get GCS object metadata."""
        try:
            if self._client is None:
                await self.initialize()

            blob = self._bucket.blob(path)
            blob.reload()

            return StorageMetadata(
                key=path,
                size_bytes=blob.size or 0,
                content_type=blob.content_type or 'application/octet-stream',
                created_at=blob.time_created or datetime.utcnow(),
                modified_at=blob.updated or datetime.utcnow(),
                checksum="",
                storage_class=blob.storage_class or 'STANDARD',
                region=self.config.region,
                bucket=self.config.bucket,
            )
        except Exception:
            return None

    async def list_objects(self, prefix: str = "") -> list[str]:
        """List GCS objects."""
        try:
            if self._client is None:
                await self.initialize()

            return [blob.name for blob in self._bucket.list_blobs(prefix=prefix)]
        except Exception:
            return []

    async def generate_signed_url(self, path: str, expiration_seconds: int = 3600) -> Optional[str]:
        """Generate signed URL."""
        try:
            if self._client is None:
                await self.initialize()

            blob = self._bucket.blob(path)
            return blob.generate_signed_url(expiration=datetime.utcnow() + timedelta(seconds=expiration_seconds))
        except Exception:
            return None


class R2StorageProvider(StorageProvider):
    """Cloudflare R2 storage provider (S3-compatible)."""

    provider_type = StorageProviderType.CLOUDFLARE_R2

    async def initialize(self) -> None:
        """Initialize R2 client (S3-compatible)."""
        try:
            import boto3
            self._client = boto3.client(
                's3',
                endpoint_url=self.config.endpoint or "https://<account>.r2.cloudflarestorage.com",
                aws_access_key_id=self.config.credentials.get("access_key"),
                aws_secret_access_key=self.config.credentials.get("secret_key"),
                region_name="auto",
            )
        except ImportError:
            print("boto3 not installed.")


class AzureBlobProvider(StorageProvider):
    """Azure Blob Storage provider."""

    provider_type = StorageProviderType.AZURE_BLOB

    async def initialize(self) -> None:
        """Initialize Azure Blob client."""
        try:
            from azure.storage.blob import BlobServiceClient
            self._client = BlobServiceClient.from_connection_string(
                self.config.credentials.get("connection_string")
            )
            self._container = self._client.get_container_client(self.config.bucket)
        except ImportError:
            print("azure-storage-blob not installed.")

    async def upload(
        self,
        data: bytes | AsyncIterator[bytes],
        destination: str,
        metadata: Optional[dict] = None
    ) -> StorageResult:
        """Upload to Azure Blob."""
        start = datetime.utcnow()

        try:
            if self._client is None:
                await self.initialize()

            blob_client = self._container.get_blob_client(destination)

            if isinstance(data, bytes):
                blob_client.upload_blob(data, overwrite=True)
            else:
                blob_client.upload_blob(data, overwrite=True)

            duration = (datetime.utcnow() - start).total_seconds() * 1000

            return StorageResult(
                success=True,
                location=f"azure://{self.config.bucket}/{destination}",
                size_bytes=len(data) if isinstance(data, bytes) else 0,
                duration_ms=duration,
            )

        except Exception as e:
            return StorageResult(success=False, location=destination, errors=[str(e)])

    async def download(self, source: str, destination_path: Optional[str] = None) -> StorageResult:
        """Download from Azure Blob."""
        start = datetime.utcnow()

        try:
            if self._client is None:
                await self.initialize()

            blob_client = self._container.get_blob_client(source)

            if destination_path:
                with open(destination_path, 'wb') as f:
                    f.write(blob_client.download_blob().readall())
            else:
                data = blob_client.download_blob().readall()

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
        """Delete from Azure Blob."""
        try:
            if self._client is None:
                await self.initialize()

            self._container.get_blob_client(path).delete_blob()
            return True
        except Exception:
            return False

    async def exists(self, path: str) -> bool:
        """Check if blob exists."""
        try:
            if self._client is None:
                await self.initialize()

            return self._container.get_blob_client(path).exists()
        except Exception:
            return False

    async def get_metadata(self, path: str) -> Optional[StorageMetadata]:
        """Get blob metadata."""
        try:
            if self._client is None:
                await self.initialize()

            blob = self._container.get_blob_client(path).get_blob_properties()

            return StorageMetadata(
                key=path,
                size_bytes=blob.size,
                content_type=blob.content_settings.content_type,
                created_at=blob.creation_time,
                modified_at=blob.last_modified,
                checksum=blob.content_settings.content_hash or "",
                storage_class="Standard",
                region=self.config.region,
                bucket=self.config.bucket,
            )
        except Exception:
            return None

    async def list_objects(self, prefix: str = "") -> list[str]:
        """List blobs."""
        try:
            if self._client is None:
                await self.initialize()

            return [blob.name for blob in self._container.list_blobs(name_starts_with=prefix)]
        except Exception:
            return []


class B2StorageProvider(StorageProvider):
    """Backblaze B2 storage provider."""

    provider_type = StorageProviderType.BACKBLAZE_B2

    async def initialize(self) -> None:
        """Initialize B2 client."""
        try:
            from b2sdk.v2 import InMemoryAccountInfo, B2Api
            info = InMemoryAccountInfo()
            self._client = B2Api(info)
            self._client.authorize_account(
                "production",
                self.config.credentials.get("application_key_id"),
                self.config.credentials.get("application_key")
            )
            self._bucket = self._client.get_bucket_by_name(self.config.bucket)
        except ImportError:
            print("b2sdk not installed.")


class MinIOProvider(StorageProvider):
    """MinIO-compatible storage provider."""

    provider_type = StorageProviderType.MINIO

    async def initialize(self) -> None:
        """Initialize MinIO client."""
        try:
            import boto3
            self._client = boto3.client(
                's3',
                endpoint_url=self.config.endpoint or "http://localhost:9000",
                aws_access_key_id=self.config.credentials.get("access_key", "minioadmin"),
                aws_secret_access_key=self.config.credentials.get("secret_key", "minioadmin"),
                region_name=self.config.region,
            )
        except ImportError:
            print("boto3 not installed.")


# Import for timedelta
from datetime import timedelta