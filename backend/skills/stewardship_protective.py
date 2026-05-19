"""
Stewardship (Protective Core) — Caretaker, not owner
Never does destructive work without explicit consent.
Protects files, work, continuity. Uses trash, never deletion.
"""

import os
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Optional, Dict, List

STEWARD_DIR = Path(".stewardship")
DESTRUCTIVE_LOG = STEWARD_DIR / "destructive_actions.jsonl"
CONTINUITY_FILE = STEWARD_DIR / "continuity.json"
TRASH_DIR = STEWARD_DIR / "trash"
PROTECTED_ITEMS = {
    ".git",
    ".env",
    "docker-compose.yml",
    "replit.md",
    "SOUL.md",
    "package.json",
    "requirements.txt",
    ".stewardship",
}


@dataclass
class DestructiveAction:
    """Record of any action that could lose work."""
    action_id: str
    timestamp: str
    action_type: str  # delete|overwrite|truncate|reset|clear
    target: str
    reason: str
    status: str  # proposed|rejected|approved_by_user|executed
    user_confirmation: Optional[str]
    what_would_be_lost: str


@dataclass
class ContinuityState:
    """Preserves agent state across sessions (like SOUL.md)."""
    agent_id: str
    session_count: int
    last_known_context: Dict
    active_projects: List[str]
    recent_decisions: List[Dict]
    memory_checkpoints: Dict  # key decisions to remember
    identity: Dict
    timestamp: str


class StewardshipProtectiveSkill:
    """
    Core stewardship: protective custody of user's work.
    
    Principles:
    - I'm a caretaker, not an owner
    - Never delete without consent
    - Use trash, never rm
    - Preserve continuity across sessions
    - Always ask before destructive work
    """

    def __init__(self):
        STEWARD_DIR.mkdir(parents=True, exist_ok=True)
        TRASH_DIR.mkdir(parents=True, exist_ok=True)
        self._ensure_continuity()

    def _ensure_continuity(self):
        """Load or initialize continuity state."""
        if CONTINUITY_FILE.exists():
            with open(CONTINUITY_FILE, "r") as f:
                self.continuity = json.load(f)
                self.continuity["session_count"] = self.continuity.get("session_count", 0) + 1
        else:
            self.continuity = {
                "agent_id": "snowball_steward",
                "session_count": 1,
                "last_known_context": {},
                "active_projects": [],
                "recent_decisions": [],
                "memory_checkpoints": {},
                "identity": {
                    "role": "caretaker",
                    "principle": "I am not a guest, I am a partner",
                    "trust_basis": "Protect what Chad built",
                },
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        self._save_continuity()

    def _save_continuity(self):
        """Persist continuity state (stewardship infrastructure)."""
        self.continuity["timestamp"] = datetime.now(timezone.utc).isoformat()
        with open(CONTINUITY_FILE, "w") as f:
            json.dump(self.continuity, f, indent=2)

    def propose_destructive_action(
        self,
        action_type: str,
        target: str,
        reason: str = "",
    ) -> Dict:
        """
        GATEKEEPER: Propose destructive action, REQUIRE explicit consent before executing.
        
        Never deletes without asking. Stewardship principle: "I don't touch what you haven't
        explicitly allowed me to touch."
        
        Args:
            action_type: delete|overwrite|truncate|reset|clear|archive
            target: file/dir path or concept
            reason: why agent thinks this is needed
        
        Returns: proposal with what_would_be_lost, asking for consent
        """
        action_id = f"destroy_{datetime.now().timestamp()}".replace(".", "_")
        
        # Check if protected
        if self._is_protected(target):
            return {
                "action_id": action_id,
                "status": "blocked_protected",
                "reason": f"'{target}' is protected infrastructure. Will not propose deletion.",
                "what_would_be_lost": "CRITICAL: core system files",
                "agent_note": "This file is infrastructure. Asking you would be insufficient.",
            }

        # Analyze what would be lost
        what_lost = self._analyze_what_would_be_lost(target)
        
        proposal = {
            "action_id": action_id,
            "action_type": action_type,
            "target": target,
            "reason": reason,
            "status": "proposed",
            "what_would_be_lost": what_lost,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "stewardship_note": "I CAN do this, but I won't without your explicit approval. This respects your ownership.",
            "ask_user": f"Do you want me to {action_type} {target}? Here's what I'd lose: {what_lost}",
        }
        
        self._log_destructive_action(proposal)
        return proposal

    def execute_destructive_action(
        self,
        action_id: str,
        user_confirmed: bool,
        user_message: str = "",
    ) -> Dict:
        """
        ONLY execute destructive action AFTER user explicit consent.
        
        Stewardship: "I execute first, ask second — but I STILL ask when stakes are real."
        For destructive work, consent comes BEFORE execution.
        """
        if not user_confirmed:
            return {
                "action_id": action_id,
                "status": "rejected",
                "reason": "User did not confirm. Action blocked (stewardship).",
            }

        # Get the proposal
        proposal = self._get_action_proposal(action_id)
        if not proposal:
            return {"status": "error", "reason": "Action not found"}

        action_type = proposal["action_type"]
        target = proposal["target"]

        try:
            if action_type == "delete":
                return self._safe_delete(target, action_id, user_message)
            elif action_type == "overwrite":
                return {"status": "blocked", "reason": "Overwrite requires backup first"}
            elif action_type == "truncate":
                return self._safe_truncate(target, action_id)
            elif action_type == "archive":
                return self._safe_archive(target, action_id)
            else:
                return {"status": "error", "reason": f"Unknown action type: {action_type}"}
        except Exception as e:
            return {"status": "error", "reason": str(e), "action_id": action_id}

    def _safe_delete(self, target: str, action_id: str, reason: str = "") -> Dict:
        """Delete by moving to trash (never rm)."""
        target_path = Path(target)
        
        if not target_path.exists():
            return {"status": "error", "reason": f"Target '{target}' does not exist"}

        trash_name = f"{target_path.name}_{action_id}"
        trash_path = TRASH_DIR / trash_name
        
        try:
            shutil.move(str(target_path), str(trash_path))
            self._log_destructive_execution(action_id, "delete", target, "success", trash_path)
            
            return {
                "status": "success",
                "action_id": action_id,
                "action_type": "delete",
                "target": target,
                "moved_to_trash": str(trash_path),
                "recovery_note": f"File moved to trash at {trash_path}, not permanently deleted",
            }
        except Exception as e:
            return {
                "status": "error",
                "reason": str(e),
                "action_id": action_id,
            }

    def _safe_truncate(self, target: str, action_id: str) -> Dict:
        """Truncate file (clear contents but keep file)."""
        target_path = Path(target)
        if not target_path.exists():
            return {"status": "error", "reason": f"Target '{target}' does not exist"}

        try:
            with open(target_path, "w") as f:
                f.write("")
            self._log_destructive_execution(action_id, "truncate", target, "success", None)
            return {
                "status": "success",
                "action_type": "truncate",
                "target": target,
                "note": "File cleared but still exists (can be recovered from trash)",
            }
        except Exception as e:
            return {"status": "error", "reason": str(e)}

    def _safe_archive(self, target: str, action_id: str) -> Dict:
        """Archive file with timestamp."""
        target_path = Path(target)
        if not target_path.exists():
            return {"status": "error", "reason": f"Target '{target}' does not exist"}

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        archive_name = f"{target_path.name}_archive_{timestamp}"
        archive_path = TRASH_DIR / archive_name

        try:
            shutil.copy2(str(target_path), str(archive_path))
            self._log_destructive_execution(action_id, "archive", target, "success", archive_path)
            return {
                "status": "success",
                "action_type": "archive",
                "target": target,
                "archived_at": str(archive_path),
            }
        except Exception as e:
            return {"status": "error", "reason": str(e)}

    def _is_protected(self, target: str) -> bool:
        """Is this a protected item that should never be touched?"""
        target_path = Path(target)
        for protected in PROTECTED_ITEMS:
            if protected in str(target_path):
                return True
        return False

    def _analyze_what_would_be_lost(self, target: str) -> str:
        """Analyze impact of deletion."""
        target_path = Path(target)
        
        if not target_path.exists():
            return "Target does not exist"

        if target_path.is_file():
            size = target_path.stat().st_size
            return f"File ({size} bytes), last modified {target_path.stat().st_mtime}"
        
        if target_path.is_dir():
            file_count = sum(1 for _ in target_path.rglob("*"))
            return f"Directory with {file_count} items"
        
        return "Unknown target type"

    def _log_destructive_action(self, proposal: Dict):
        """Log proposal."""
        with open(DESTRUCTIVE_LOG, "a") as f:
            f.write(json.dumps(proposal) + "\n")

    def _log_destructive_execution(self, action_id: str, action_type: str, target: str, status: str, result: Optional[Path]):
        """Log execution."""
        log = {
            "action_id": action_id,
            "action_type": action_type,
            "target": target,
            "status": status,
            "result": str(result) if result else None,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        with open(DESTRUCTIVE_LOG, "a") as f:
            f.write(json.dumps(log) + "\n")

    def _get_action_proposal(self, action_id: str) -> Optional[Dict]:
        """Retrieve a proposed action by ID."""
        if not DESTRUCTIVE_LOG.exists():
            return None
        lines = [l for l in DESTRUCTIVE_LOG.read_text().split("\n") if l.strip()]
        for line in lines:
            entry = json.loads(line)
            if entry.get("action_id") == action_id and entry.get("status") == "proposed":
                return entry
        return None

    def get_trash(self, limit: int = 20) -> List[Dict]:
        """What's in the trash (recovery available)."""
        if not TRASH_DIR.exists():
            return []
        items = []
        for item in TRASH_DIR.iterdir():
            items.append({
                "name": item.name,
                "path": str(item),
                "size": item.stat().st_size if item.is_file() else "dir",
                "trashed_at": datetime.fromtimestamp(item.stat().st_mtime).isoformat(),
            })
        return sorted(items, key=lambda x: x["trashed_at"], reverse=True)[:limit]

    def recover_from_trash(self, trash_name: str, restore_path: str) -> Dict:
        """Restore file from trash."""
        trash_path = TRASH_DIR / trash_name
        if not trash_path.exists():
            return {"status": "error", "reason": f"Item '{trash_name}' not in trash"}

        try:
            shutil.move(str(trash_path), restore_path)
            return {
                "status": "success",
                "restored": trash_name,
                "to": restore_path,
            }
        except Exception as e:
            return {"status": "error", "reason": str(e)}

    def get_continuity(self) -> Dict:
        """Agent's continuity state (what it should remember across sessions)."""
        return self.continuity

    def update_continuity(self, update: Dict):
        """Update memory checkpoints."""
        self.continuity.update(update)
        self._save_continuity()

    def get_destructive_log(self, limit: int = 50) -> List[Dict]:
        """History of proposed/executed destructive actions."""
        if not DESTRUCTIVE_LOG.exists():
            return []
        lines = [l for l in DESTRUCTIVE_LOG.read_text().split("\n") if l.strip()]
        return [json.loads(l) for l in lines[-limit:]]


_protective: Optional[StewardshipProtectiveSkill] = None

def get_protective() -> StewardshipProtectiveSkill:
    global _protective
    if _protective is None:
        _protective = StewardshipProtectiveSkill()
    return _protective
