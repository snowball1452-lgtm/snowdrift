# pythonserver.py
# Sovereign Memory Sidecar — port 8765
# Runs independently so memory survives backend restarts.
# Start with: uvicorn pythonserver:app --host 0.0.0.0 --port 8765

import logging
from pathlib import Path
from typing import Optional, List
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

from sovereign_memory_prod import SovereignMemoryProd
from self_healing import SelfHealingEngine

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

# ==================== PYDANTIC MODELS ====================

class WriteRequest(BaseModel):
    content: str
    embedding: Optional[List[float]] = None
    sigma: float = 0.5
    modality: str = "text"
    source: str = "api"
    session_id: Optional[str] = None

class WriteResponse(BaseModel):
    address: str
    leaf_hash: str
    session_id: str
    timestamp: str

class QueryRequest(BaseModel):
    query_text: str = ""
    query_embedding: Optional[List[float]] = None
    query_sigma: float = 1.0
    top_k: int = 5
    min_relevance: float = 0.01
    session_id: Optional[str] = None

class QueryResult(BaseModel):
    address: str
    content: str
    relevance: float
    sigma: float
    verified: bool
    modality: str
    source: str
    timestamp: str
    corruption_detected: bool

class ProveRequest(BaseModel):
    address: str
    session_id: Optional[str] = None

class ProveResponse(BaseModel):
    address: str
    leaf_hash: str
    root_hash: str
    valid: bool
    failure_reason: str = ""

class HealthResponse(BaseModel):
    status: str
    timestamp: str
    total_memories: int
    root_hash: str
    sessions: List[str]

# ==================== APP ====================

app = FastAPI(title="Sovereign Memory Sidecar", version="1.0.0", description="Port 8765")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_memory_instances: dict[str, SovereignMemoryProd] = {}
_healer = SelfHealingEngine()

def get_memory(session_id: Optional[str] = None) -> SovereignMemoryProd:
    sid = session_id or "default"
    if sid not in _memory_instances:
        _memory_instances[sid] = SovereignMemoryProd(session_id=sid)
    return _memory_instances[sid]

# ==================== ENDPOINTS ====================

@app.post("/memory/write", response_model=WriteResponse)
async def write_memory(req: WriteRequest):
    try:
        mem = get_memory(req.session_id)
        address = mem.write(
            content=req.content,
            embedding=req.embedding,
            sigma=req.sigma,
            modality=req.modality,
            source=req.source,
        )
        leaf_hash = ""
        if address in mem._leaf_cache:
            leaf_hash = mem._leaf_cache[address].leaf_hash
        return WriteResponse(
            address=address,
            leaf_hash=leaf_hash,
            session_id=mem.session_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )
    except Exception as e:
        logger.error(f"Write failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/memory/query", response_model=List[QueryResult])
async def query_memory(req: QueryRequest):
    try:
        mem = get_memory(req.session_id)
        results = mem.query(
            query_text=req.query_text,
            query_embedding=req.query_embedding,
            query_sigma=req.query_sigma,
            top_k=req.top_k,
            min_relevance=req.min_relevance,
        )
        return [
            QueryResult(
                address=r["address"],
                content=r["content"],
                relevance=r["relevance"],
                sigma=r["sigma"],
                verified=r.get("verified", False),
                modality=r.get("modality", "unknown"),
                source=r.get("source", "unknown"),
                timestamp=r.get("timestamp", ""),
                corruption_detected=r.get("corruption_detected", False),
            )
            for r in results
        ]
    except Exception as e:
        logger.error(f"Query failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/memory/prove", response_model=ProveResponse)
async def prove_memory(req: ProveRequest):
    try:
        mem = get_memory(req.session_id)
        proof = mem.prove(req.address)
        return ProveResponse(
            address=proof.address,
            leaf_hash=proof.leaf_hash,
            root_hash=proof.root_hash,
            valid=proof.valid,
            failure_reason=proof.failure_reason,
        )
    except Exception as e:
        logger.error(f"Prove failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/memory/verify")
async def verify_all(session_id: Optional[str] = None):
    try:
        mem = get_memory(session_id)
        return mem.verify_all()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/memory/stats")
async def memory_stats(session_id: Optional[str] = None):
    try:
        mem = get_memory(session_id)
        stats = mem.stats()
        integrity = mem.verify_all()
        return {"stats": stats, "integrity": integrity, "sessions": list(_memory_instances.keys())}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health", response_model=HealthResponse)
async def health(session_id: Optional[str] = None):
    mem = get_memory(session_id)
    stats = mem.stats()
    return HealthResponse(
        status="ok",
        timestamp=datetime.now(timezone.utc).isoformat(),
        total_memories=stats["total_memories"],
        root_hash=stats["root_hash"],
        sessions=list(_memory_instances.keys()),
    )


@app.post("/healing/check")
async def healing_check():
    try:
        result = await _healer.run_health_check()
        return {
            "score": result.score,
            "overall_status": result.overall_status,
            "checks": [
                {"component": c.component, "status": c.status, "message": c.message}
                for c in result.checks
            ],
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==================== MAIN ====================

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8765, log_level="info")
