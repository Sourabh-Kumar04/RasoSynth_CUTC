"""
Dataset Versioning & Incremental Updates

Supports version control, diff-based updates, and incremental synchronization.
"""

import hashlib
import json
from typing import Optional, List
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class VersionStatus(Enum):
    """Status of a dataset version."""
    DRAFT = "draft"
    PUBLISHED = "published"
    DEPRECATED = "deprecated"
    DELETED = "deleted"


@dataclass
class DatasetVersion:
    """Represents a version of a dataset."""
    version_id: str
    version_number: str  # e.g., "1.0.0", "1.1.0"
    dataset_id: str
    created_at: datetime
    created_by: str
    status: VersionStatus
    size_bytes: int
    checksum: str
    # Change tracking
    changes_summary: str
    added_samples: int = 0
    removed_samples: int = 0
    modified_samples: int = 0
    # Storage
    storage_location: Optional[str] = None
    metadata_location: Optional[str] = None
    # Compatibility
    parent_version: Optional[str] = None
    tags: list[str] = field(default_factory=list)
    notes: str = ""
    metadata: dict = field(default_factory=dict)


@dataclass
class VersionDiff:
    """Represents differences between versions."""
    from_version: str
    to_version: str
    added: list[dict]  # New items
    removed: list[dict]  # Removed items
    modified: list[tuple[dict, dict]]  # (old, new) pairs
    size_diff_bytes: int
    item_count_diff: int


@dataclass
class VersionManifest:
    """Manifest containing all versions of a dataset."""
    dataset_id: str
    current_version: str
    versions: list[DatasetVersion]
    total_size_bytes: int
    total_versions: int
    created_at: datetime
    updated_at: datetime


class DatasetVersionManager:
    """Manage dataset versions and updates."""

    def __init__(self, storage_location: Optional[str] = None):
        self.storage_location = storage_location
        self._versions: dict[str, dict[str, DatasetVersion]] = {}  # dataset_id -> version_id -> Version

    def create_version(
        self,
        dataset_id: str,
        data: list[dict],
        version_number: str,
        created_by: str = "system",
        notes: str = ""
    ) -> DatasetVersion:
        """Create a new version of a dataset."""
        import uuid

        version_id = str(uuid.uuid4())
        total_size = sum(len(json.dumps(item)) for item in data)
        checksum = hashlib.sha256(json.dumps(data).encode()).hexdigest()

        version = DatasetVersion(
            version_id=version_id,
            version_number=version_number,
            dataset_id=dataset_id,
            created_at=datetime.utcnow(),
            created_by=created_by,
            status=VersionStatus.DRAFT,
            size_bytes=total_size,
            checksum=checksum,
            changes_summary=f"Version {version_number} created",
            notes=notes,
        )

        # Store version
        if dataset_id not in self._versions:
            self._versions[dataset_id] = {}
        self._versions[dataset_id][version_id] = version

        return version

    def publish_version(self, dataset_id: str, version_id: str) -> DatasetVersion:
        """Publish a version (make it current)."""
        version = self._versions.get(dataset_id, {}).get(version_id)
        if not version:
            raise ValueError(f"Version {version_id} not found")

        version.status = VersionStatus.PUBLISHED

        # Deprecate other versions
        for v in self._versions.get(dataset_id, {}).values():
            if v.version_id != version_id and v.status == VersionStatus.PUBLISHED:
                v.status = VersionStatus.DEPRECATED

        return version

    def get_version(self, dataset_id: str, version_id: str) -> Optional[DatasetVersion]:
        """Get a specific version."""
        return self._versions.get(dataset_id, {}).get(version_id)

    def get_current_version(self, dataset_id: str) -> Optional[DatasetVersion]:
        """Get the current (published) version."""
        versions = self._versions.get(dataset_id, {})
        for v in versions.values():
            if v.status == VersionStatus.PUBLISHED:
                return v
        # Return latest if no published version
        if versions:
            return max(versions.values(), key=lambda x: x.created_at)
        return None

    def list_versions(self, dataset_id: str) -> list[DatasetVersion]:
        """List all versions of a dataset."""
        versions = list(self._versions.get(dataset_id, {}).values())
        return sorted(versions, key=lambda x: x.created_at, reverse=True)

    def delete_version(self, dataset_id: str, version_id: str) -> bool:
        """Delete a version (soft delete)."""
        version = self._versions.get(dataset_id, {}).get(version_id)
        if version:
            version.status = VersionStatus.DELETED
            return True
        return False

    def compare_versions(
        self,
        dataset_id: str,
        from_version_id: str,
        to_version_id: str,
        from_data: list[dict],
        to_data: list[dict]
    ) -> VersionDiff:
        """Compare two versions and identify differences."""
        from_v = self._versions.get(dataset_id, {}).get(from_version_id)
        to_v = self._versions.get(dataset_id, {}).get(to_version_id)

        # Create lookup sets
        from_keys = {json.dumps(item, sort_keys=True): item for item in from_data}
        to_keys = {json.dumps(item, sort_keys=True): item for item in to_data}

        from_set = set(from_keys.keys())
        to_set = set(to_keys.keys())

        # Find differences
        added_keys = to_set - from_set
        removed_keys = from_set - to_set

        added = [to_keys[k] for k in added_keys]
        removed = [from_keys[k] for k in removed_keys]

        # For modified, find items with same key but different content
        modified = []
        for key in from_set & to_set:
            if from_keys[key] != to_keys[key]:
                modified.append((from_keys[key], to_keys[key]))

        size_diff = (to_v.size_bytes - from_v.size_bytes) if to_v and from_v else 0

        return VersionDiff(
            from_version=from_version_id,
            to_version=to_version_id,
            added=added,
            removed=removed,
            modified=modified,
            size_diff_bytes=size_diff,
            item_count_diff=len(to_data) - len(from_data)
        )

    def rollback_to_version(
        self,
        dataset_id: str,
        version_id: str,
        available_data: dict[str, list[dict]]
    ) -> Optional[list[dict]]:
        """Rollback to a previous version."""
        version = self.get_version(dataset_id, version_id)
        if not version:
            return None

        # Check if data is available
        if version_id not in available_data:
            # Try to reconstruct from parent versions
            return self._reconstruct_version(dataset_id, version_id, available_data)

        return available_data.get(version_id)

    def _reconstruct_version(
        self,
        dataset_id: str,
        version_id: str,
        available_data: dict[str, list[dict]]
    ) -> Optional[list[dict]]:
        """Attempt to reconstruct a version from available data."""
        version = self.get_version(dataset_id, version_id)
        if not version or not version.parent_version:
            return None

        # Get parent version
        parent_data = available_data.get(version.parent_version)
        if not parent_data:
            return None

        # Apply reverse of changes (simplified)
        return parent_data  # In real implementation, would apply reverse diffs

    def get_version_history(self, dataset_id: str) -> VersionManifest:
        """Get complete version history."""
        versions = self.list_versions(dataset_id)

        return VersionManifest(
            dataset_id=dataset_id,
            current_version=versions[0].version_id if versions else "",
            versions=versions,
            total_size_bytes=sum(v.size_bytes for v in versions),
            total_versions=len(versions),
            created_at=versions[0].created_at if versions else datetime.utcnow(),
            updated_at=versions[0].created_at if versions else datetime.utcnow(),
        )

    def tag_version(
        self,
        dataset_id: str,
        version_id: str,
        tag: str
    ) -> DatasetVersion:
        """Add a tag to a version."""
        version = self._versions.get(dataset_id, {}).get(version_id)
        if version and tag not in version.tags:
            version.tags.append(tag)
        return version

    def find_versions_by_tag(
        self,
        dataset_id: str,
        tag: str
    ) -> list[DatasetVersion]:
        """Find versions with a specific tag."""
        return [
            v for v in self._versions.get(dataset_id, {}).values()
            if tag in v.tags
        ]


class IncrementalUpdater:
    """Handle incremental updates between versions."""

    def __init__(self, version_manager: DatasetVersionManager):
        self.version_manager = version_manager

    async def create_incremental_update(
        self,
        dataset_id: str,
        current_data: list[dict],
        previous_version_id: str
    ) -> tuple[DatasetVersion, list[dict]]:
        """Create an incremental update package."""
        previous_version = self.version_manager.get_version(dataset_id, previous_version_id)
        if not previous_version:
            raise ValueError(f"Previous version {previous_version_id} not found")

        # Compare versions
        diff = self.version_manager.compare_versions(
            dataset_id,
            previous_version_id,
            "new",  # Placeholder
            [],  # Would need previous data
            current_data
        )

        # Create incremental package
        incremental_data = {
            "base_version": previous_version_id,
            "version_number": self._increment_minor(previous_version.version_number),
            "added": diff.added,
            "removed": diff.removed,
            "modified": [new for _, new in diff.modified],
            "timestamp": datetime.utcnow().isoformat(),
        }

        # Create new version
        new_version = self.version_manager.create_version(
            dataset_id=dataset_id,
            data=current_data,
            version_number=incremental_data["version_number"],
            notes=f"Incremental update from {previous_version.version_number}"
        )
        new_version.parent_version = previous_version_id
        new_version.added_samples = len(diff.added)
        new_version.removed_samples = len(diff.removed)
        new_version.modified_samples = len(diff.modified)
        new_version.changes_summary = (
            f"Added: {len(diff.added)}, Removed: {len(diff.removed)}, "
            f"Modified: {len(diff.modified)}"
        )

        return new_version, current_data  # In real impl, would return incremental package

    def apply_incremental_update(
        self,
        base_data: list[dict],
        incremental_package: dict
    ) -> list[dict]:
        """Apply an incremental update to base data."""
        result = list(base_data)

        # Remove deleted items
        removed_hashes = {json.dumps(item, sort_keys=True) for item in incremental_package.get("removed", [])}
        result = [item for item in result if json.dumps(item, sort_keys=True) not in removed_hashes]

        # Add new items
        result.extend(incremental_package.get("added", []))

        # Apply modifications
        for old_item, new_item in incremental_package.get("modified", []):
            old_key = json.dumps(old_item, sort_keys=True)
            for i, item in enumerate(result):
                if json.dumps(item, sort_keys=True) == old_key:
                    result[i] = new_item
                    break

        return result

    def _increment_minor(self, version: str) -> str:
        """Increment minor version number."""
        parts = version.split(".")
        if len(parts) >= 2:
            minor = int(parts[-1]) + 1
            return ".".join(parts[:-1] + [str(minor)])
        return f"{version}.1"

    def create_patch_download(
        self,
        dataset_id: str,
        from_version_id: str,
        to_version_id: str
    ) -> dict:
        """Create a patch file for download."""
        from_v = self.version_manager.get_version(dataset_id, from_version_id)
        to_v = self.version_manager.get_version(dataset_id, to_version_id)

        return {
            "from_version": from_version_id,
            "to_version": to_version_id,
            "from_size": from_v.size_bytes if from_v else 0,
            "to_size": to_v.size_bytes if to_v else 0,
            "patch_size": abs((to_v.size_bytes if to_v else 0) - (from_v.size_bytes if from_v else 0)),
            "download_url": f"/datasets/{dataset_id}/patches/{from_version_id}_{to_version_id}",
        }

    async def verify_patch_integrity(
        self,
        base_data: list[dict],
        patch_data: dict,
        target_data: list[dict]
    ) -> bool:
        """Verify that applying patch produces target data."""
        try:
            result = self.apply_incremental_update(base_data, patch_data)

            # Compare checksums
            result_hash = hashlib.sha256(json.dumps(result, sort_keys=True).encode()).hexdigest()
            target_hash = hashlib.sha256(json.dumps(target_data, sort_keys=True).encode()).hexdigest()

            return result_hash == target_hash
        except Exception:
            return False