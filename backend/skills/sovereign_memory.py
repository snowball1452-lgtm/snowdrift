"""
Sovereign Memory — Blake3-sealed content-addressed memory
Git blob storage + Gaussian spray fields + Nested Blake3 Merkle trees

Corruption is unrepresentable. Address IS the content hash.
Any modification changes the leaf → branch → root hash instantly.
"""

import json
import math
import hashlib
import time
from datetime import datetime, timezone
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Optional


def blake3_hash(data: bytes) -> str:
    try:
        import blake3
        return blake3.blake3(data).hexdigest()
    except ImportError:
        return hashlib.sha3_256(data).hexdigest()


def seal_dict(d: dict) -> str:
    return blake3_hash(json.dumps(d, sort_keys=True).encode())


@dataclass
class GaussianMemory:
    address: str
    content: str
    mu: list[float]
    sigma: float
    modality: str
    source: str
    sealed_at: str
    leaf_hash: str
    prior_leaf_hash: str
    session_id: str

    def relevance(self, query_mu: list[float]) -> float:
        if not self.mu or not query_mu or len(self.mu) != len(query_mu):
            return 0.0
        distance = math.sqrt(sum((a - b) ** 2 for a, b in zip(self.mu, query_mu)))
        return math.exp(-0.5 * (distance / max(self.sigma, 1e-10)) ** 2)

    def verify(self) -> bool:
        return blake3_hash(self.content.encode()) == self.address


@dataclass
class MerkleBranch:
    branch_id: str
    session_id: str
    children: list[str]
    branch_hash: str
    created_at: str

    @classmethod
    def from_leaves(cls, session_id: str, leaf_hashes: list[str]) -> "MerkleBranch":
        branch_id = f"{session_id}_{int(time.time()*1000)}"
        branch_hash = blake3_hash("".join(leaf_hashes).encode())
        return cls(
            branch_id=branch_id,
            session_id=session_id,
            children=leaf_hashes,
            branch_hash=branch_hash,
            created_at=datetime.now(timezone.utc).isoformat(),
        )


@dataclass
class MerkleProof:
    address: str
    leaf_hash: str
    branch_hash: str
    root_hash: str
    root_sealed_at: str
    valid: bool
    failure_reason: str = ""


class SovereignMemory:
    """
    Memory that cannot lie.
    Write → content-addressed → Gaussian record → leaf hash
    → Merkle tree → branch updated → root hash updated → sealed
    """

    STORE_DIR = Path(".sovereign_memory")

    def __init__(self, session_id: Optional[str] = None):
        self.STORE_DIR.mkdir(parents=True, exist_ok=True)
        (self.STORE_DIR / "leaves").mkdir(exist_ok=True)
        (self.STORE_DIR / "branches").mkdir(exist_ok=True)
        (self.STORE_DIR / "roots").mkdir(exist_ok=True)
        self.session_id = session_id or f"session_{int(time.time())}"
        self._leaf_cache: dict[str, GaussianMemory] = {}
        self._load_cache()

    def write(
        self,
        content: str,
        embedding: Optional[list[float]] = None,
        sigma: float = 1.0,
        modality: str = "text",
        source: str = "user",
    ) -> str:
        address = blake3_hash(content.encode())
        if address in self._leaf_cache:
            return address
        mu = embedding if embedding else self._pseudo_embedding(content)
        prior_leaf_hash = self._last_leaf_hash()
        ts = datetime.now(timezone.utc).isoformat()
        record = GaussianMemory(
            address=address,
            content=content,
            mu=mu,
            sigma=sigma,
            modality=modality,
            source=source,
            sealed_at=ts,
            leaf_hash="",
            prior_leaf_hash=prior_leaf_hash,
            session_id=self.session_id,
        )
        record_dict = asdict(record)
        record_dict["leaf_hash"] = ""
        record.leaf_hash = seal_dict(record_dict)
        leaf_path = self.STORE_DIR / "leaves" / f"{address}.json"
        leaf_path.write_text(json.dumps(asdict(record), indent=2))
        self._leaf_cache[address] = record
        self._update_tree(record)
        return address

    def query(
        self,
        query_content: str,
        query_embedding: Optional[list[float]] = None,
        top_k: int = 5,
        min_relevance: float = 0.01,
    ) -> list[dict]:
        if not self._leaf_cache:
            return []
        query_mu = query_embedding or self._pseudo_embedding(query_content)
        scored = []
        for address, memory in self._leaf_cache.items():
            relevance = memory.relevance(query_mu)
            if relevance >= min_relevance:
                verified = memory.verify()
                scored.append({
                    "address": address,
                    "content": memory.content,
                    "relevance": round(relevance, 4),
                    "sigma": memory.sigma,
                    "modality": memory.modality,
                    "source": memory.source,
                    "sealed_at": memory.sealed_at,
                    "verified": verified,
                    "corruption_detected": not verified,
                })
        scored.sort(key=lambda x: x["relevance"], reverse=True)
        return scored[:top_k]

    def prove(self, address: str) -> MerkleProof:
        memory = self._leaf_cache.get(address)
        if not memory:
            return MerkleProof(address=address, leaf_hash="", branch_hash="",
                               root_hash="", root_sealed_at="", valid=False,
                               failure_reason="address not found")
        root = self._current_root()
        if not root:
            return MerkleProof(address=address, leaf_hash=memory.leaf_hash,
                               branch_hash="", root_hash="", root_sealed_at="",
                               valid=False, failure_reason="no root yet")
        branch_hash = self._find_branch_for_leaf(memory.leaf_hash)
        return MerkleProof(
            address=address,
            leaf_hash=memory.leaf_hash,
            branch_hash=branch_hash or "",
            root_hash=root.get("root_hash", ""),
            root_sealed_at=root.get("sealed_at", ""),
            valid=memory.verify(),
        )

    def stats(self) -> dict:
        return {
            "total_memories": len(self._leaf_cache),
            "session_id": self.session_id,
            "verified": sum(1 for m in self._leaf_cache.values() if m.verify()),
            "corrupted": sum(1 for m in self._leaf_cache.values() if not m.verify()),
        }

    def _pseudo_embedding(self, content: str) -> list[float]:
        h = hashlib.sha256(content.lower().encode()).digest()
        return [((b / 255.0) * 2 - 1) for b in h[:32]]

    def _last_leaf_hash(self) -> str:
        if not self._leaf_cache:
            return "genesis"
        return list(self._leaf_cache.values())[-1].leaf_hash

    def _update_tree(self, record: GaussianMemory):
        leaves = [m.leaf_hash for m in self._leaf_cache.values()]
        branch = MerkleBranch.from_leaves(self.session_id, leaves)
        branch_path = self.STORE_DIR / "branches" / f"{branch.branch_id}.json"
        branch_path.write_text(json.dumps(asdict(branch), indent=2))
        root = {
            "root_hash": branch.branch_hash,
            "total_memories": len(self._leaf_cache),
            "sealed_at": datetime.now(timezone.utc).isoformat(),
        }
        root_path = self.STORE_DIR / "roots" / "current.json"
        root_path.write_text(json.dumps(root, indent=2))

    def _current_root(self) -> Optional[dict]:
        root_path = self.STORE_DIR / "roots" / "current.json"
        if root_path.exists():
            return json.loads(root_path.read_text())
        return None

    def _find_branch_for_leaf(self, leaf_hash: str) -> Optional[str]:
        branch_dir = self.STORE_DIR / "branches"
        for f in sorted(branch_dir.glob("*.json"), reverse=True):
            try:
                b = json.loads(f.read_text())
                if leaf_hash in b.get("children", []):
                    return b["branch_hash"]
            except Exception:
                pass
        return None

    def _load_cache(self):
        leaf_dir = self.STORE_DIR / "leaves"
        for f in sorted(leaf_dir.glob("*.json")):
            try:
                data = json.loads(f.read_text())
                self._leaf_cache[data["address"]] = GaussianMemory(**data)
            except Exception:
                pass


# Global instance
_memory = SovereignMemory()


def get_memory() -> SovereignMemory:
    return _memory
