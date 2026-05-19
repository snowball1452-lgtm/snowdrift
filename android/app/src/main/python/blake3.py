"""
blake3 stdlib shim for Android (ARM64).

The real blake3 package has no ARM64 wheel, so this module provides
a pure-Python fallback using hashlib.sha256 as a deterministic hash.

This is NOT blake3 — it's a compatible interface for seal/verify use cases
where the hash just needs to be deterministic, not cryptographically blake3.
"""

import hashlib
import json
from typing import Optional


def blake3(data: bytes) -> "Blake3Hash":
    """Create a Blake3Hash object from bytes (uses sha256 under the hood)."""
    return Blake3Hash(data)


class Blake3Hash:
    """Compatibility shim for blake3.blake3()."""

    def __init__(self, data: bytes = b""):
        self._hasher = hashlib.sha256(data)

    def update(self, data: bytes) -> "Blake3Hash":
        self._hasher.update(data)
        return self

    def hexdigest(self) -> str:
        return self._hasher.hexdigest()

    def digest(self) -> bytes:
        return self._hasher.digest()


def hash_data(data, sort_keys: bool = True) -> str:
    """Convenience: hash any JSON-serializable data to a hex string."""
    if isinstance(data, str):
        data = data.encode()
    elif not isinstance(data, bytes):
        data = json.dumps(data, sort_keys=sort_keys).encode()
    return blake3(data).hexdigest()
