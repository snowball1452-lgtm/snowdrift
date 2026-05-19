"""
SnowballBot Self-Healing Engine
Detection → Recovery → Rebuild → Verification → Growth

Monitors system health, creates snapshots, auto-recovers from failures,
and tracks the agent's evolution over time.
"""

import os
import sys
import json
import shutil
import zipfile
import asyncio
import logging
import platform
import psutil
import hashlib
from pathlib import Path
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime, timedelta
from pydantic import BaseModel, Field

from storage_backend import StorageBackend, LocalStorageBackend, AzureBlobBackend, get_storage_backend

logger = logging.getLogger(__name__)


# ==================== MODELS ====================

class HealthCheck(BaseModel):
    """Single health check result."""
    component: str
    status: str  # "healthy", "degraded", "critical", "unknown"
    response_time_ms: float = 0
    message: str = ""
    checked_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    details: Dict[str, Any] = {}


class SystemHealth(BaseModel):
    """Overall system health snapshot."""
    id: str = Field(default_factory=lambda: datetime.utcnow().strftime("%Y%m%d_%H%M%S"))
    overall_status: str = "unknown"  # "healthy", "degraded", "critical"
    score: int = 100  # 0-100
    checks: List[HealthCheck] = []
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    uptime_seconds: float = 0
    cpu_percent: float = 0
    memory_percent: float = 0
    disk_percent: float = 0


class Snapshot(BaseModel):
    """A point-in-time snapshot of the system."""
    id: str = Field(default_factory=lambda: datetime.utcnow().strftime("snap_%Y%m%d_%H%M%S"))
    name: str = ""
    description: str = ""
    health_score: int = 100
    file_key: str = ""  # Storage key
    size_mb: float = 0
    file_count: int = 0
    checksum: str = ""
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    includes: Dict[str, bool] = {"backend": True, "frontend_src": True, "config": True}
    metadata: Dict[str, Any] = {}


class RecoveryLog(BaseModel):
    """Record of a recovery attempt."""
    id: str = Field(default_factory=lambda: datetime.utcnow().strftime("rec_%Y%m%d_%H%M%S"))
    trigger: str = ""  # "auto", "manual"
    reason: str = ""
    snapshot_used: str = ""
    phases: List[Dict[str, Any]] = []
    status: str = "pending"  # "pending", "in_progress", "success", "failed"
    started_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    completed_at: Optional[str] = None
    verification_passed: bool = False


class EvolutionEntry(BaseModel):
    """Tracks a growth event."""
    id: str = Field(default_factory=lambda: datetime.utcnow().strftime("evo_%Y%m%d_%H%M%S"))
    event_type: str  # "skill_learned", "tool_added", "recovery_survived", "config_evolved", "capability_added"
    description: str
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    data: Dict[str, Any] = {}


class HealConfig(BaseModel):
    """Self-healing configuration."""
    enabled: bool = True
    check_interval_seconds: int = 60
    auto_recover: bool = False  # Auto-trigger recovery on critical
    health_threshold: int = 40  # Score below this triggers recovery
    max_snapshots: int = 10
    storage_type: str = "local"  # "local" or "azure"
    storage_path: str = "/tmp/snowball_snapshots"
    azure_connection_string: str = ""
    azure_container: str = "snowball-snapshots"
    snapshot_includes: Dict[str, bool] = {
        "backend": True,
        "frontend_src": True,
        "config": True,
    }


# ==================== SELF-HEALING ENGINE ====================

class SelfHealingEngine:
    """
    The core self-healing engine for SnowballBot.
    
    Lifecycle:
    1. Detection  → Continuous health monitoring
    2. Recovery   → Pull clean snapshot from storage
    3. Rebuild    → Extract and regenerate environment
    4. Verify     → Confirm everything is functional
    5. Evolve     → Track growth over time
    """

    def __init__(self, db=None):
        self.db = db
        # Use writable workspace path instead of /app
        _workspace = os.environ.get("WORKSPACE_DIR", str(Path(__file__).parent.parent))
        self.config = HealConfig(
            storage_path=str(Path(_workspace) / "snapshots")
        )
        self.storage: Optional[StorageBackend] = None
        self._monitor_task: Optional[asyncio.Task] = None
        self._start_time = datetime.utcnow()
        self._last_health: Optional[SystemHealth] = None
        self._recovery_in_progress = False
        
        # Paths
        self.backend_dir = Path(_workspace) / "backend"
        self.frontend_dir = Path(_workspace) / "frontend"
        self.temp_dir = Path("/tmp/snowball_heal")

    async def initialize(self):
        """Load config from DB and set up storage."""
        if self.db is not None:
            saved = await self.db.heal_config.find_one({"id": "default"})
            if saved:
                saved.pop("_id", None)
                self.config = HealConfig(**saved)
        
        self._init_storage()
        logger.info(f"SelfHealingEngine initialized. Storage: {self.config.storage_type} @ {self.config.storage_path}")

    def _init_storage(self):
        """Initialize storage backend based on config."""
        self.storage = get_storage_backend({
            "type": self.config.storage_type,
            "path": self.config.storage_path,
            "connection_string": self.config.azure_connection_string,
            "container_name": self.config.azure_container,
        })

    async def save_config(self):
        """Persist config to DB."""
        if self.db is not None:
            data = self.config.dict()
            data["id"] = "default"
            await self.db.heal_config.update_one(
                {"id": "default"}, {"$set": data}, upsert=True
            )

    # ==================== PHASE 1: DETECTION ====================

    async def run_health_check(self) -> SystemHealth:
        """Run a comprehensive health check across all subsystems."""
        import httpx
        import time

        checks: List[HealthCheck] = []
        
        # 1. Backend API health
        try:
            start = time.time()
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get("http://localhost:8000/api/health")
                elapsed = (time.time() - start) * 1000
                data = resp.json()
                checks.append(HealthCheck(
                    component="backend_api",
                    status="healthy" if resp.status_code == 200 else "critical",
                    response_time_ms=round(elapsed, 1),
                    message=f"Status {resp.status_code}",
                    details=data
                ))
        except Exception as e:
            checks.append(HealthCheck(
                component="backend_api",
                status="critical",
                message=f"Backend unreachable: {str(e)[:100]}"
            ))

        # 2. Database connectivity
        try:
            start = time.time()
            if self.db is not None:
                await self.db.command("ping")
                elapsed = (time.time() - start) * 1000
                checks.append(HealthCheck(
                    component="database",
                    status="healthy",
                    response_time_ms=round(elapsed, 1),
                    message="MongoDB responsive"
                ))
            else:
                checks.append(HealthCheck(
                    component="database",
                    status="unknown",
                    message="No DB reference"
                ))
        except Exception as e:
            checks.append(HealthCheck(
                component="database",
                status="critical",
                message=f"DB error: {str(e)[:100]}"
            ))

        # 3. LLM Provider availability
        try:
            start = time.time()
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get("http://localhost:8000/api/providers")
                elapsed = (time.time() - start) * 1000
                providers = resp.json()
                checks.append(HealthCheck(
                    component="llm_providers",
                    status="healthy" if len(providers) > 0 else "degraded",
                    response_time_ms=round(elapsed, 1),
                    message=f"{len(providers)} providers available",
                    details={"count": len(providers)}
                ))
        except Exception as e:
            checks.append(HealthCheck(
                component="llm_providers",
                status="degraded",
                message=f"Provider check failed: {str(e)[:100]}"
            ))

        # 4. GhostWright engine
        try:
            start = time.time()
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.get("http://localhost:8000/api/ghost/status")
                elapsed = (time.time() - start) * 1000
                data = resp.json()
                checks.append(HealthCheck(
                    component="ghostwright",
                    status="healthy",
                    response_time_ms=round(elapsed, 1),
                    message=f"Sessions: {data.get('active_sessions', 0)}",
                    details=data
                ))
        except Exception as e:
            checks.append(HealthCheck(
                component="ghostwright",
                status="degraded",
                message=f"GhostWright: {str(e)[:80]}"
            ))

        # 5. Swarm engine
        try:
            start = time.time()
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.get("http://localhost:8000/api/swarm/status")
                elapsed = (time.time() - start) * 1000
                data = resp.json()
                checks.append(HealthCheck(
                    component="swarm",
                    status="healthy",
                    response_time_ms=round(elapsed, 1),
                    message="Swarm online",
                    details=data
                ))
        except Exception as e:
            checks.append(HealthCheck(
                component="swarm",
                status="degraded",
                message=f"Swarm: {str(e)[:80]}"
            ))

        # 6. Ollama local brain
        try:
            start = time.time()
            ollama_url = "http://localhost:11434"
            if self.db is not None:
                settings_doc = await self.db.settings.find_one({"id": "default"})
                if settings_doc:
                    ollama_url = settings_doc.get("ollama_base_url", ollama_url)
            async with httpx.AsyncClient(timeout=4) as client:
                resp = await client.get(f"{ollama_url.rstrip('/')}/api/tags")
                elapsed = (time.time() - start) * 1000
                models = resp.json().get("models", [])
                checks.append(HealthCheck(
                    component="ollama_local",
                    status="healthy" if resp.status_code == 200 else "degraded",
                    response_time_ms=round(elapsed, 1),
                    message=f"{len(models)} model(s) loaded",
                    details={"models": [m.get("name", "") for m in models[:5] if m.get("name")], "url": ollama_url},
                ))
        except Exception as e:
            checks.append(HealthCheck(
                component="ollama_local",
                status="degraded",
                message=f"Ollama offline: {str(e)[:60]}",
            ))

        # 7. System resources
        try:
            cpu = psutil.cpu_percent(interval=0.5)
            mem = psutil.virtual_memory()
            disk = psutil.disk_usage("/")
            
            resource_status = "healthy"
            if cpu > 90 or mem.percent > 90 or disk.percent > 95:
                resource_status = "critical"
            elif cpu > 70 or mem.percent > 70 or disk.percent > 80:
                resource_status = "degraded"
            
            checks.append(HealthCheck(
                component="system_resources",
                status=resource_status,
                message=f"CPU: {cpu}%, MEM: {mem.percent}%, DISK: {disk.percent}%",
                details={
                    "cpu_percent": cpu,
                    "memory_percent": mem.percent,
                    "memory_total_gb": round(mem.total / (1024**3), 2),
                    "disk_percent": disk.percent,
                    "disk_free_gb": round(disk.free / (1024**3), 2),
                }
            ))
        except Exception as e:
            checks.append(HealthCheck(
                component="system_resources",
                status="unknown",
                message=f"Resource check failed: {str(e)[:80]}"
            ))

        # 7. File integrity check (key files exist)
        key_files = [
            self.backend_dir / "server.py",
            self.backend_dir / "ghostwright.py",
            self.backend_dir / "swarm.py",
            self.backend_dir / "self_healing.py",
            self.frontend_dir / "app" / "index.tsx",
            self.frontend_dir / "app" / "_layout.tsx",
            self.frontend_dir / "package.json",
        ]
        missing = [str(f) for f in key_files if not f.exists()]
        checks.append(HealthCheck(
            component="file_integrity",
            status="healthy" if not missing else "critical",
            message=f"{len(key_files) - len(missing)}/{len(key_files)} key files intact",
            details={"missing": missing} if missing else {}
        ))

        # Calculate overall score
        score = 100
        status_weights = {"healthy": 0, "degraded": -10, "critical": -25, "unknown": -5}
        for check in checks:
            score += status_weights.get(check.status, -5)
        score = max(0, min(100, score))

        overall = "healthy"
        if score < 40:
            overall = "critical"
        elif score < 70:
            overall = "degraded"

        uptime = (datetime.utcnow() - self._start_time).total_seconds()

        health = SystemHealth(
            overall_status=overall,
            score=score,
            checks=checks,
            uptime_seconds=round(uptime, 1),
            cpu_percent=next((c.details.get("cpu_percent", 0) for c in checks if c.component == "system_resources"), 0),
            memory_percent=next((c.details.get("memory_percent", 0) for c in checks if c.component == "system_resources"), 0),
            disk_percent=next((c.details.get("disk_percent", 0) for c in checks if c.component == "system_resources"), 0),
        )

        self._last_health = health

        # Store in DB
        if self.db is not None:
            await self.db.health_checks.insert_one(health.dict())

        # Auto-recover check
        if self.config.auto_recover and score < self.config.health_threshold and not self._recovery_in_progress:
            logger.warning(f"Health score {score} below threshold {self.config.health_threshold}. Triggering auto-recovery.")
            asyncio.create_task(self.auto_recover(health))

        return health

    async def get_health_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent health check history."""
        if self.db is None:
            return []
        cursor = self.db.health_checks.find({}, {"_id": 0}).sort("timestamp", -1).limit(limit)
        return await cursor.to_list(limit)

    # ==================== PHASE 2: SNAPSHOT / RECOVERY ====================

    async def create_snapshot(self, name: str = "", description: str = "") -> Snapshot:
        """Create a point-in-time snapshot of the current system state."""
        if not self.storage:
            self._init_storage()

        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        snap_id = f"snap_{timestamp}"
        zip_name = f"{snap_id}.zip"

        # Create temp directory for staging
        stage_dir = self.temp_dir / snap_id
        stage_dir.mkdir(parents=True, exist_ok=True)

        file_count = 0
        try:
            # Collect backend files
            if self.config.snapshot_includes.get("backend", True):
                backend_stage = stage_dir / "backend"
                backend_stage.mkdir(parents=True, exist_ok=True)
                for f in self.backend_dir.rglob("*"):
                    if f.is_file() and "__pycache__" not in str(f) and ".pyc" not in str(f):
                        relative = f.relative_to(self.backend_dir)
                        dest = backend_stage / relative
                        dest.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(str(f), str(dest))
                        file_count += 1

            # Collect frontend source files (NOT node_modules)
            if self.config.snapshot_includes.get("frontend_src", True):
                frontend_stage = stage_dir / "frontend"
                frontend_stage.mkdir(parents=True, exist_ok=True)
                exclude_dirs = {"node_modules", ".expo", ".metro-cache", "dist", ".cache", "web-build"}
                for f in self.frontend_dir.rglob("*"):
                    if f.is_file() and not any(ex in str(f) for ex in exclude_dirs):
                        relative = f.relative_to(self.frontend_dir)
                        dest = frontend_stage / relative
                        dest.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(str(f), str(dest))
                        file_count += 1

            # Collect config files
            if self.config.snapshot_includes.get("config", True):
                config_stage = stage_dir / "config"
                config_stage.mkdir(parents=True, exist_ok=True)
                # Save current health state
                if self._last_health:
                    with open(config_stage / "last_health.json", "w") as f:
                        json.dump(self._last_health.dict(), f, indent=2)
                # Save healing config
                with open(config_stage / "heal_config.json", "w") as f:
                    json.dump(self.config.dict(), f, indent=2)
                # Save evolution state
                if self.db is not None:
                    evolutions = await self.db.evolution.find({}, {"_id": 0}).to_list(100)
                    with open(config_stage / "evolution.json", "w") as f:
                        json.dump(evolutions, f, indent=2)
                file_count += 3

            # Create zip
            zip_path = self.temp_dir / zip_name
            with zipfile.ZipFile(str(zip_path), 'w', zipfile.ZIP_DEFLATED) as zf:
                for f in stage_dir.rglob("*"):
                    if f.is_file():
                        zf.write(str(f), str(f.relative_to(stage_dir)))

            # Calculate checksum
            sha256 = hashlib.sha256()
            with open(zip_path, "rb") as f:
                for chunk in iter(lambda: f.read(8192), b""):
                    sha256.update(chunk)

            # Store to backend
            receipt = await self.storage.store(
                str(zip_path),
                zip_name,
                metadata={
                    "name": name or snap_id,
                    "description": description,
                    "created_at": datetime.utcnow().isoformat(),
                    "health_score": self._last_health.score if self._last_health else -1,
                }
            )

            snap = Snapshot(
                id=snap_id,
                name=name or snap_id,
                description=description or f"Snapshot at {timestamp}",
                health_score=self._last_health.score if self._last_health else -1,
                file_key=zip_name,
                size_mb=receipt.get("size_mb", 0),
                file_count=file_count,
                checksum=sha256.hexdigest()[:16],
                includes=self.config.snapshot_includes,
            )

            # Store snapshot metadata in DB
            if self.db is not None:
                await self.db.snapshots.insert_one(snap.dict())

            # Track evolution
            await self.track_evolution("snapshot_created", f"Snapshot '{snap.name}' created ({snap.size_mb}MB, {file_count} files)")

            logger.info(f"Snapshot created: {snap.id} ({snap.size_mb}MB, {file_count} files)")
            return snap

        finally:
            # Cleanup temp files
            shutil.rmtree(str(stage_dir), ignore_errors=True)
            zip_cleanup = self.temp_dir / zip_name
            if zip_cleanup.exists():
                zip_cleanup.unlink(missing_ok=True)

    async def list_snapshots(self) -> List[Dict[str, Any]]:
        """List all available snapshots."""
        if self.db is not None:
            cursor = self.db.snapshots.find({}, {"_id": 0}).sort("created_at", -1)
            return await cursor.to_list(50)
        
        # Fallback to storage listing
        if self.storage:
            return await self.storage.list_items()
        return []

    async def delete_snapshot(self, snapshot_id: str) -> bool:
        """Delete a snapshot."""
        if self.db is not None:
            snap = await self.db.snapshots.find_one({"id": snapshot_id})
            if snap and self.storage:
                await self.storage.delete(snap.get("file_key", ""))
            await self.db.snapshots.delete_one({"id": snapshot_id})
        return True

    # ==================== PHASE 3: REBUILD ====================

    async def recover(self, snapshot_id: str = None, trigger: str = "manual") -> RecoveryLog:
        """
        Recover from a snapshot.
        If no snapshot_id given, uses the latest healthy snapshot.
        """
        if self._recovery_in_progress:
            return RecoveryLog(
                status="failed",
                reason="Recovery already in progress",
                trigger=trigger
            )

        self._recovery_in_progress = True
        log = RecoveryLog(trigger=trigger)

        try:
            # Phase 1: Find snapshot
            log.phases.append({"phase": "locate_snapshot", "status": "started", "time": datetime.utcnow().isoformat()})
            
            if snapshot_id:
                snap_meta = await self.db.snapshots.find_one({"id": snapshot_id}) if self.db else None
            else:
                # Find latest healthy snapshot
                snap_meta = None
                if self.db is not None:
                    snap_meta = await self.db.snapshots.find_one(
                        {"health_score": {"$gte": 70}},
                        sort=[("created_at", -1)]
                    )
                if not snap_meta and self.db:
                    # Any snapshot
                    snap_meta = await self.db.snapshots.find_one(sort=[("created_at", -1)])

            if not snap_meta:
                log.phases[-1]["status"] = "failed"
                log.phases[-1]["error"] = "No snapshots available"
                log.status = "failed"
                log.reason = "No snapshots found"
                return log

            snap_meta.pop("_id", None)
            log.snapshot_used = snap_meta.get("id", "")
            log.reason = f"Recovering from snapshot: {snap_meta.get('name', snap_meta.get('id'))}"
            log.phases[-1]["status"] = "complete"
            log.phases[-1]["snapshot"] = snap_meta.get("id")

            # Phase 2: Retrieve snapshot
            log.phases.append({"phase": "retrieve", "status": "started", "time": datetime.utcnow().isoformat()})
            
            extract_dir = self.temp_dir / "recovery"
            extract_dir.mkdir(parents=True, exist_ok=True)
            zip_path = extract_dir / "recovery.zip"

            file_key = snap_meta.get("file_key", "")
            retrieved = await self.storage.retrieve(file_key, str(zip_path))
            if not retrieved:
                log.phases[-1]["status"] = "failed"
                log.phases[-1]["error"] = f"Could not retrieve {file_key} from storage"
                log.status = "failed"
                return log
            
            log.phases[-1]["status"] = "complete"
            log.phases[-1]["size_mb"] = round(zip_path.stat().st_size / (1024*1024), 2)

            # Phase 3: Extract and rebuild
            log.phases.append({"phase": "rebuild", "status": "started", "time": datetime.utcnow().isoformat()})
            log.status = "in_progress"

            content_dir = extract_dir / "content"
            content_dir.mkdir(parents=True, exist_ok=True)

            with zipfile.ZipFile(str(zip_path), 'r') as zf:
                zf.extractall(str(content_dir))

            # Restore backend files
            backend_src = content_dir / "backend"
            if backend_src.exists():
                for f in backend_src.rglob("*"):
                    if f.is_file():
                        relative = f.relative_to(backend_src)
                        dest = self.backend_dir / relative
                        dest.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(str(f), str(dest))

            # Restore frontend source (NOT node_modules)
            frontend_src = content_dir / "frontend"
            if frontend_src.exists():
                for f in frontend_src.rglob("*"):
                    if f.is_file() and "node_modules" not in str(f):
                        relative = f.relative_to(frontend_src)
                        dest = self.frontend_dir / relative
                        dest.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(str(f), str(dest))

            log.phases[-1]["status"] = "complete"

            # Phase 4: Restart services
            log.phases.append({"phase": "restart_services", "status": "started", "time": datetime.utcnow().isoformat()})
            
            try:
                proc = await asyncio.create_subprocess_shell(
                    "sudo supervisorctl restart backend",
                    stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
                )
                await asyncio.wait_for(proc.communicate(), timeout=15)
                
                proc2 = await asyncio.create_subprocess_shell(
                    "sudo supervisorctl restart expo",
                    stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
                )
                await asyncio.wait_for(proc2.communicate(), timeout=15)
                
                log.phases[-1]["status"] = "complete"
            except Exception as e:
                log.phases[-1]["status"] = "warning"
                log.phases[-1]["error"] = str(e)[:100]

            # Phase 5: Wait for services to come up
            await asyncio.sleep(5)

            # Store recovery log
            if self.db is not None:
                await self.db.recovery_logs.insert_one(log.dict())

            log.status = "success"
            log.completed_at = datetime.utcnow().isoformat()

            # Track evolution
            await self.track_evolution(
                "recovery_survived",
                f"Successfully recovered from snapshot {snap_meta.get('name', snap_meta.get('id'))}",
                {"trigger": trigger, "snapshot": snap_meta.get("id")}
            )

            logger.info(f"Recovery complete: {log.id}")
            return log

        except Exception as e:
            log.status = "failed"
            log.phases.append({"phase": "error", "status": "failed", "error": str(e), "time": datetime.utcnow().isoformat()})
            logger.error(f"Recovery failed: {e}")
            return log
        finally:
            self._recovery_in_progress = False
            shutil.rmtree(str(self.temp_dir / "recovery"), ignore_errors=True)

    async def auto_recover(self, health: SystemHealth):
        """Triggered automatically when health drops below threshold."""
        logger.warning(f"AUTO-RECOVERY triggered. Health score: {health.score}")
        result = await self.recover(trigger="auto")
        if result.status == "success":
            # Run verification
            await self.verify()

    # ==================== PHASE 4: VERIFICATION ====================

    async def verify(self) -> Dict[str, Any]:
        """Run post-recovery verification to confirm everything is working."""
        import time
        start = time.time()

        # Run a fresh health check
        health = await self.run_health_check()
        
        verification = {
            "timestamp": datetime.utcnow().isoformat(),
            "health_score": health.score,
            "overall_status": health.overall_status,
            "duration_ms": round((time.time() - start) * 1000, 1),
            "components": {},
            "passed": health.score >= 60,
        }

        # Convert health checks to JSON-serializable format
        for check in health.checks:
            # Ensure check is converted to dict if it's a Pydantic model
            if hasattr(check, 'dict'):
                check_dict = check.dict()
            else:
                check_dict = check
            
            verification["components"][check_dict.get("component", "unknown")] = {
                "status": check_dict.get("status", "unknown"),
                "response_time_ms": check_dict.get("response_time_ms", 0),
                "message": check_dict.get("message", ""),
            }

        # Store verification (but don't include ObjectId in return)
        if self.db is not None:
            # Create a copy for storage that might get ObjectId added
            storage_verification = verification.copy()
            await self.db.verifications.insert_one(storage_verification)

        # Return clean verification data without any MongoDB ObjectIds
        return verification

    # ==================== PHASE 5: EVOLUTION ====================

    async def track_evolution(self, event_type: str, description: str, data: Dict[str, Any] = None):
        """Track an evolution/growth event."""
        entry = EvolutionEntry(
            event_type=event_type,
            description=description,
            data=data or {},
        )
        
        if self.db is not None:
            await self.db.evolution.insert_one(entry.dict())

        logger.info(f"Evolution: [{event_type}] {description}")

    async def get_evolution(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get evolution history — the agent's growth timeline."""
        if self.db is None:
            return []
        cursor = self.db.evolution.find({}, {"_id": 0}).sort("timestamp", -1).limit(limit)
        return await cursor.to_list(limit)

    async def get_growth_metrics(self) -> Dict[str, Any]:
        """Calculate growth metrics from evolution history."""
        if self.db is None:
            return {"total_events": 0}

        pipeline = [
            {"$group": {
                "_id": "$event_type",
                "count": {"$sum": 1},
                "latest": {"$max": "$timestamp"}
            }}
        ]
        results = await self.db.evolution.aggregate(pipeline).to_list(50)
        
        by_type = {r["_id"]: {"count": r["count"], "latest": r["latest"]} for r in results}
        total = sum(r["count"] for r in results)

        # Count snapshots, recoveries
        snap_count = await self.db.snapshots.count_documents({})
        recovery_count = await self.db.recovery_logs.count_documents({})
        successful_recoveries = await self.db.recovery_logs.count_documents({"status": "success"})

        # Uptime
        uptime = (datetime.utcnow() - self._start_time).total_seconds()

        return {
            "total_events": total,
            "by_type": by_type,
            "snapshots_created": snap_count,
            "recoveries_attempted": recovery_count,
            "recoveries_successful": successful_recoveries,
            "uptime_hours": round(uptime / 3600, 2),
            "health_score": self._last_health.score if self._last_health else -1,
            "is_growing": total > 0,
        }

    # ==================== MONITORING LOOP ====================

    async def start_monitoring(self):
        """Start the background health monitoring loop."""
        if self._monitor_task and not self._monitor_task.done():
            return
        self._monitor_task = asyncio.create_task(self._monitor_loop())
        logger.info("Health monitoring started")

    async def stop_monitoring(self):
        """Stop the background monitoring loop."""
        if self._monitor_task:
            self._monitor_task.cancel()
            self._monitor_task = None
            logger.info("Health monitoring stopped")

    async def _monitor_loop(self):
        """Background loop that periodically checks health."""
        while True:
            try:
                if self.config.enabled:
                    await self.run_health_check()
                await asyncio.sleep(self.config.check_interval_seconds)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Monitor loop error: {e}")
                await asyncio.sleep(30)

    def get_status(self) -> Dict[str, Any]:
        """Get current engine status."""
        return {
            "enabled": self.config.enabled,
            "monitoring": bool(self._monitor_task and not self._monitor_task.done()),
            "last_health": self._last_health.dict() if self._last_health else None,
            "recovery_in_progress": self._recovery_in_progress,
            "storage": self.storage.get_info() if self.storage else None,
            "uptime_seconds": round((datetime.utcnow() - self._start_time).total_seconds(), 1),
        }
