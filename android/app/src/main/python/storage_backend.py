"""
Storage Backend Abstraction Layer
Supports: Local filesystem (C:/, D:/, Linux paths), Azure Blob (future), In-environment
"""

import os
import shutil
import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import List, Optional, Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)


class StorageBackend(ABC):
    """Abstract storage interface for snapshot management."""

    @abstractmethod
    async def store(self, source_path: str, destination_key: str, metadata: Dict[str, Any] = None) -> Dict[str, Any]:
        """Store a file to the backend. Returns storage receipt."""
        pass

    @abstractmethod
    async def retrieve(self, key: str, destination_path: str) -> bool:
        """Retrieve a file from storage to a local path."""
        pass

    @abstractmethod
    async def list_items(self, prefix: str = "") -> List[Dict[str, Any]]:
        """List stored items."""
        pass

    @abstractmethod
    async def delete(self, key: str) -> bool:
        """Delete an item from storage."""
        pass

    @abstractmethod
    async def exists(self, key: str) -> bool:
        """Check if an item exists."""
        pass

    @abstractmethod
    def get_info(self) -> Dict[str, Any]:
        """Get storage backend info."""
        pass


class LocalStorageBackend(StorageBackend):
    """
    Local filesystem storage. Works with any path:
    - Windows: C:/SnowballBot/snapshots, D:/backups
    - Linux: /home/user/snapshots, /mnt/data
    - Current environment: /app/snapshots
    """

    def __init__(self, base_path: str = "/app/snapshots"):
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)
        self.metadata_dir = self.base_path / ".metadata"
        self.metadata_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"LocalStorageBackend initialized at: {self.base_path}")

    async def store(self, source_path: str, destination_key: str, metadata: Dict[str, Any] = None) -> Dict[str, Any]:
        """Copy a file to the local storage directory."""
        try:
            dest = self.base_path / destination_key
            dest.parent.mkdir(parents=True, exist_ok=True)

            shutil.copy2(source_path, str(dest))

            file_size = dest.stat().st_size
            receipt = {
                "key": destination_key,
                "path": str(dest),
                "size_bytes": file_size,
                "size_mb": round(file_size / (1024 * 1024), 2),
                "stored_at": datetime.utcnow().isoformat(),
                "backend": "local",
                "base_path": str(self.base_path),
            }

            # Store metadata
            if metadata:
                receipt["metadata"] = metadata
            
            import json
            meta_file = self.metadata_dir / f"{destination_key.replace('/', '_')}.json"
            meta_file.parent.mkdir(parents=True, exist_ok=True)
            with open(meta_file, 'w') as f:
                json.dump(receipt, f, indent=2)

            logger.info(f"Stored {source_path} -> {dest} ({receipt['size_mb']} MB)")
            return receipt
        except Exception as e:
            logger.error(f"Storage failed: {e}")
            raise

    async def retrieve(self, key: str, destination_path: str) -> bool:
        """Copy a file from storage to the destination."""
        try:
            source = self.base_path / key
            if not source.exists():
                logger.error(f"Key not found in storage: {key}")
                return False

            Path(destination_path).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(str(source), destination_path)
            logger.info(f"Retrieved {key} -> {destination_path}")
            return True
        except Exception as e:
            logger.error(f"Retrieval failed: {e}")
            return False

    async def list_items(self, prefix: str = "") -> List[Dict[str, Any]]:
        """List all stored items."""
        items = []
        import json
        
        search_path = self.base_path / prefix if prefix else self.base_path
        if not search_path.exists():
            return items

        for f in sorted(search_path.rglob("*.zip")):
            relative = f.relative_to(self.base_path)
            meta_file = self.metadata_dir / f"{str(relative).replace('/', '_')}.json"
            
            meta = {}
            if meta_file.exists():
                try:
                    with open(meta_file) as mf:
                        meta = json.load(mf)
                except Exception:
                    pass

            items.append({
                "key": str(relative),
                "path": str(f),
                "size_bytes": f.stat().st_size,
                "size_mb": round(f.stat().st_size / (1024 * 1024), 2),
                "modified": datetime.fromtimestamp(f.stat().st_mtime).isoformat(),
                "metadata": meta.get("metadata", {}),
            })

        return items

    async def delete(self, key: str) -> bool:
        """Delete an item from storage."""
        try:
            target = self.base_path / key
            if target.exists():
                target.unlink()
                # Remove metadata too
                meta_file = self.metadata_dir / f"{key.replace('/', '_')}.json"
                if meta_file.exists():
                    meta_file.unlink()
                logger.info(f"Deleted: {key}")
                return True
            return False
        except Exception as e:
            logger.error(f"Delete failed: {e}")
            return False

    async def exists(self, key: str) -> bool:
        return (self.base_path / key).exists()

    def get_info(self) -> Dict[str, Any]:
        total, used, free = shutil.disk_usage(str(self.base_path))
        return {
            "type": "local",
            "base_path": str(self.base_path),
            "disk_total_gb": round(total / (1024**3), 2),
            "disk_used_gb": round(used / (1024**3), 2),
            "disk_free_gb": round(free / (1024**3), 2),
            "writable": os.access(str(self.base_path), os.W_OK),
        }


class AzureBlobBackend(StorageBackend):
    """
    Azure Blob Storage backend. Ready for when credentials are available.
    Requires: AZURE_STORAGE_CONNECTION_STRING or AZURE_STORAGE_SAS_TOKEN in env.
    """

    def __init__(self, connection_string: str = None, container_name: str = "snowball-snapshots"):
        self.connection_string = connection_string or os.environ.get("AZURE_STORAGE_CONNECTION_STRING", "")
        self.container_name = container_name
        self.configured = bool(self.connection_string)
        
        if self.configured:
            logger.info(f"AzureBlobBackend initialized for container: {container_name}")
        else:
            logger.warning("AzureBlobBackend: No connection string. Azure storage not available.")

    async def store(self, source_path: str, destination_key: str, metadata: Dict[str, Any] = None) -> Dict[str, Any]:
        if not self.configured:
            raise RuntimeError("Azure Blob Storage not configured. Set AZURE_STORAGE_CONNECTION_STRING.")
        
        # Azure SDK integration point
        # from azure.storage.blob import BlobServiceClient
        # blob_service = BlobServiceClient.from_connection_string(self.connection_string)
        # container = blob_service.get_container_client(self.container_name)
        # with open(source_path, "rb") as data:
        #     container.upload_blob(destination_key, data, overwrite=True, metadata=metadata)
        
        raise NotImplementedError("Azure Blob upload: Install azure-storage-blob and uncomment implementation")

    async def retrieve(self, key: str, destination_path: str) -> bool:
        if not self.configured:
            return False
        raise NotImplementedError("Azure Blob download: Install azure-storage-blob and uncomment implementation")

    async def list_items(self, prefix: str = "") -> List[Dict[str, Any]]:
        if not self.configured:
            return []
        raise NotImplementedError("Azure Blob list: Install azure-storage-blob and uncomment implementation")

    async def delete(self, key: str) -> bool:
        if not self.configured:
            return False
        raise NotImplementedError("Azure Blob delete: Install azure-storage-blob and uncomment implementation")

    async def exists(self, key: str) -> bool:
        if not self.configured:
            return False
        raise NotImplementedError("Azure Blob exists: Install azure-storage-blob and uncomment implementation")

    def get_info(self) -> Dict[str, Any]:
        return {
            "type": "azure_blob",
            "container": self.container_name,
            "configured": self.configured,
            "connection_set": bool(self.connection_string),
        }


def get_storage_backend(config: Dict[str, Any] = None) -> StorageBackend:
    """Factory function to create the right storage backend based on config."""
    if config is None:
        config = {}

    backend_type = config.get("type", "local")
    
    if backend_type == "azure":
        return AzureBlobBackend(
            connection_string=config.get("connection_string"),
            container_name=config.get("container_name", "snowball-snapshots")
        )
    else:
        # Local filesystem — works with any path
        base_path = config.get("path", "/app/snapshots")
        return LocalStorageBackend(base_path=base_path)
