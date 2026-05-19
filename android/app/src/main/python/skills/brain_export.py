"""Brain Export/Import — Export and import learned skills, tools, and knowledge.
Cherry-picked from main_ish. Android-adapted: export path uses APP_FILES_DIR
env var (set by Kotlin before daemon launches) instead of hardcoded /app/backend/.
"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

# Android: APP_FILES_DIR is set by PythonDaemonManager before launch
# Falls back to /tmp for desktop/cloud runs
_BASE = Path(os.environ.get("APP_FILES_DIR", "/tmp"))
EXPORT_DIR = _BASE / "brain_exports"


class BrainExporter:
    """Export and import the agent's learned knowledge."""

    def __init__(self):
        try:
            EXPORT_DIR.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass  # Read-only filesystem — exports won't persist, but won't crash

    async def export_brain(self, db, name: str = "") -> Dict:
        """Export all learned data: tools, skills, conversations, memories."""
        timestamp   = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        export_name = name or f"brain_{timestamp}"
        export_path = EXPORT_DIR / f"{export_name}.json"

        brain_data: Dict = {
            "name":       export_name,
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "version":    "1.0",
            "tools":      [],
            "skills":     [],
            "settings":   {},
            "evolution":  [],
        }

        if db is not None:
            try:
                brain_data["tools"]     = await db.tools.find({}, {"_id": 0}).to_list(200)
                brain_data["skills"]    = await db.skills.find({}, {"_id": 0}).to_list(200)
                settings = await db.settings.find_one({"id": "default"})
                if settings:
                    settings.pop("_id", None)
                    brain_data["settings"] = settings
                brain_data["evolution"] = await (
                    db.evolution.find({}, {"_id": 0}).sort("timestamp", -1).limit(100).to_list(100)
                )
            except Exception:
                pass  # MongoDB offline — export what we have

        try:
            export_path.write_text(json.dumps(brain_data, indent=2, default=str))
            size_kb = round(export_path.stat().st_size / 1024, 1)
            path_str = str(export_path)
        except Exception as e:
            return {"error": f"Could not write export: {e}"}

        return {
            "name":           export_name,
            "path":           path_str,
            "size_kb":        size_kb,
            "tools_count":    len(brain_data["tools"]),
            "skills_count":   len(brain_data["skills"]),
            "evolution_count": len(brain_data["evolution"]),
        }

    async def import_brain(self, db, file_path: str) -> Dict:
        """Import brain data from a JSON export."""
        path = Path(file_path)
        if not path.exists():
            return {"error": "File not found"}
        try:
            data = json.loads(path.read_text())
        except Exception as e:
            return {"error": f"Invalid JSON: {e}"}

        imported = {"tools": 0, "skills": 0, "evolution": 0}

        if db is not None:
            try:
                for tool in data.get("tools", []):
                    await db.tools.update_one({"name": tool.get("name")}, {"$set": tool}, upsert=True)
                    imported["tools"] += 1
                for skill in data.get("skills", []):
                    await db.skills.update_one({"name": skill.get("name")}, {"$set": skill}, upsert=True)
                    imported["skills"] += 1
                for evo in data.get("evolution", []):
                    await db.evolution.insert_one(evo)
                    imported["evolution"] += 1
            except Exception:
                pass

        return {"imported": imported, "from_file": str(path)}

    def list_exports(self) -> List[Dict]:
        exports = []
        try:
            for f in sorted(EXPORT_DIR.glob("*.json"), reverse=True):
                try:
                    data = json.loads(f.read_text())
                    exports.append({
                        "name":        data.get("name", f.stem),
                        "exported_at": data.get("exported_at", ""),
                        "size_kb":     round(f.stat().st_size / 1024, 1),
                    })
                except Exception:
                    exports.append({"name": f.stem, "size_kb": round(f.stat().st_size / 1024, 1)})
        except Exception:
            pass
        return exports


_exporter: Optional[BrainExporter] = None

def get_exporter() -> BrainExporter:
    global _exporter
    if _exporter is None:
        _exporter = BrainExporter()
    return _exporter
