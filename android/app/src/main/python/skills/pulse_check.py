"""Pulse Check — Quick system vitals and operational health.
Cherry-picked from main_ish. Android-adapted: disk check falls back
gracefully when '/' isn't accessible (Chaquopy sandbox).
"""

import os
import platform
from datetime import datetime, timezone
from typing import Dict

try:
    import psutil
    _HAS_PSUTIL = True
except ImportError:
    _HAS_PSUTIL = False


class PulseCheck:
    """Quick operational vitals check. Safe on Android/Chaquopy."""

    def check(self) -> Dict:
        ts = datetime.now(timezone.utc).isoformat()

        if not _HAS_PSUTIL:
            return {
                "timestamp": ts,
                "system":  {"platform": platform.system(), "python": platform.python_version()},
                "process": {"pid": os.getpid()},
                "status":  "unknown",
                "note":    "psutil unavailable on this build",
            }

        cpu = psutil.cpu_percent(interval=0.3)
        mem = psutil.virtual_memory()
        proc = psutil.Process(os.getpid())
        proc_mem = proc.memory_info()

        # Disk check — '/' may be unreadable inside Android sandbox
        disk_info = {}
        for path in ("/", "/data", os.path.expanduser("~")):
            try:
                d = psutil.disk_usage(path)
                disk_info = {
                    "disk_path":         path,
                    "disk_total_gb":     round(d.total / (1024**3), 2),
                    "disk_used_percent": d.percent,
                }
                break
            except (PermissionError, FileNotFoundError):
                continue

        system = {
            "platform":          platform.system(),
            "python":            platform.python_version(),
            "cpu_percent":       cpu,
            "cpu_count":         psutil.cpu_count(),
            "memory_total_gb":   round(mem.total / (1024**3), 2),
            "memory_used_percent": mem.percent,
        }
        system.update(disk_info)

        return {
            "timestamp": ts,
            "system": system,
            "process": {
                "pid":       proc.pid,
                "memory_mb": round(proc_mem.rss / (1024**2), 1),
                "threads":   proc.num_threads(),
            },
            "status": self._status(cpu, mem.percent, disk_info.get("disk_used_percent", 0)),
        }

    def _status(self, cpu: float, mem: float, disk: float) -> str:
        if cpu > 90 or mem > 90 or disk > 95: return "critical"
        if cpu > 70 or mem > 70 or disk > 80: return "warning"
        return "healthy"


_pulse = None

def get_pulse() -> PulseCheck:
    global _pulse
    if _pulse is None:
        _pulse = PulseCheck()
    return _pulse
