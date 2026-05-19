"""
Reasoning Level 11: Cognitive Load Manager
Monitors user's mental bandwidth and adapts agent verbosity accordingly.
Busy user → 1-line answers. Deep focus → full explanations.
Prevents information overload from an over-eager agent.
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Optional

LOAD_DIR = Path(".reasoning_cognitive")
STATE_FILE = LOAD_DIR / "state.json"
HISTORY_FILE = LOAD_DIR / "history.jsonl"

VERBOSITY_LEVELS = {
    "minimal": {
        "description": "1–2 sentences max. Only the essential answer.",
        "max_words": 40,
        "use_bullet_points": False,
        "include_examples": False,
        "include_reasoning": False,
    },
    "concise": {
        "description": "Short paragraph. Core answer + 1 reason.",
        "max_words": 120,
        "use_bullet_points": True,
        "include_examples": False,
        "include_reasoning": False,
    },
    "normal": {
        "description": "Balanced response. Answer + context + 1 example.",
        "max_words": 300,
        "use_bullet_points": True,
        "include_examples": True,
        "include_reasoning": True,
    },
    "detailed": {
        "description": "Full explanation with reasoning, examples, and alternatives.",
        "max_words": 700,
        "use_bullet_points": True,
        "include_examples": True,
        "include_reasoning": True,
    },
}

LOAD_INDICATORS = {
    "high_load": {
        "triggers": ["busy", "quick question", "briefly", "tldr", "short version", "in a rush", "hurry"],
        "signals": ["multiple questions in quick succession", "short messages"],
    },
    "low_load": {
        "triggers": ["explain in detail", "tell me everything", "walk me through", "deep dive", "comprehensive"],
        "signals": ["long messages", "follow-up questions asking for more"],
    },
}


@dataclass
class CognitiveState:
    """Current estimated cognitive load of the user."""
    load_level: str          # low | medium | high | critical
    verbosity: str           # minimal | concise | normal | detailed
    messages_last_5min: int
    avg_message_length: float
    last_updated: str
    notes: str


class ReasoningCognitiveLoadSkill:
    """
    Level 11 Advanced Reasoning: Cognitive load detection + verbosity adaptation.
    The agent that knows when to STFU and when to go deep.
    """

    def __init__(self):
        LOAD_DIR.mkdir(parents=True, exist_ok=True)
        self._state = self._load_state()

    def _load_state(self) -> dict:
        if STATE_FILE.exists():
            with open(STATE_FILE) as f:
                return json.load(f)
        return {
            "load_level": "medium",
            "verbosity": "normal",
            "messages_last_5min": 0,
            "avg_message_length": 50,
            "last_updated": datetime.now(timezone.utc).isoformat(),
            "notes": "Default state",
        }

    def _save_state(self):
        with open(STATE_FILE, "w") as f:
            json.dump(self._state, f, indent=2)

    def assess(self, message: str, message_history: list[str] = None) -> dict:
        """
        Assess cognitive load from incoming message + history.
        Returns: load level, recommended verbosity, style instructions.
        """
        message_lower = message.lower()
        history = message_history or []

        # Count recent messages (simulated)
        recent_count = len(history)
        avg_length = sum(len(m) for m in [message] + history) / max(len([message] + history), 1)

        # Explicit load signals from message
        explicit_load = "medium"
        for sig in LOAD_INDICATORS["high_load"]["triggers"]:
            if sig in message_lower:
                explicit_load = "high"
                break
        if explicit_load == "medium":
            for sig in LOAD_INDICATORS["low_load"]["triggers"]:
                if sig in message_lower:
                    explicit_load = "low"
                    break

        # Infer from message patterns
        if explicit_load == "medium":
            if avg_length < 25 and recent_count > 5:
                explicit_load = "high"
            elif avg_length > 200:
                explicit_load = "low"
            elif recent_count > 10:
                explicit_load = "high"

        # Map load to verbosity
        verbosity_map = {
            "critical": "minimal",
            "high": "concise",
            "medium": "normal",
            "low": "detailed",
        }
        verbosity = verbosity_map.get(explicit_load, "normal")

        # Build recommendation
        style = VERBOSITY_LEVELS[verbosity]
        result = {
            "load_level": explicit_load,
            "verbosity": verbosity,
            "style": style,
            "instruction": f"{style['description']} Max {style['max_words']} words.",
            "include_bullets": style["use_bullet_points"],
            "include_examples": style["include_examples"],
            "assessed_at": datetime.now(timezone.utc).isoformat(),
        }

        # Update state
        self._state.update({
            "load_level": explicit_load,
            "verbosity": verbosity,
            "messages_last_5min": recent_count,
            "avg_message_length": round(avg_length, 1),
            "last_updated": result["assessed_at"],
            "notes": f"Signal: {'explicit' if explicit_load != 'medium' else 'inferred'}",
        })
        self._save_state()
        self._log_assessment(result)
        return result

    def get_current_verbosity(self) -> dict:
        """Get current verbosity setting for agent to use."""
        state = self._state
        verbosity = state.get("verbosity", "normal")
        style = VERBOSITY_LEVELS.get(verbosity, VERBOSITY_LEVELS["normal"])
        return {
            "verbosity": verbosity,
            "load_level": state.get("load_level", "medium"),
            "style": style,
            "instruction": f"{style['description']} Max {style['max_words']} words.",
        }

    def set_override(self, verbosity: str) -> dict:
        """Manual override for verbosity (user sets preference explicitly)."""
        if verbosity not in VERBOSITY_LEVELS:
            return {"error": f"Invalid verbosity. Use: {list(VERBOSITY_LEVELS.keys())}"}
        self._state["verbosity"] = verbosity
        self._state["load_level"] = "manual_override"
        self._state["notes"] = "User manually set verbosity"
        self._save_state()
        return {"status": "override_set", "verbosity": verbosity, "style": VERBOSITY_LEVELS[verbosity]}

    def reset(self) -> dict:
        """Reset to auto-detection mode."""
        self._state = {
            "load_level": "medium",
            "verbosity": "normal",
            "messages_last_5min": 0,
            "avg_message_length": 50,
            "last_updated": datetime.now(timezone.utc).isoformat(),
            "notes": "Reset to auto",
        }
        self._save_state()
        return {"status": "reset", "verbosity": "normal"}

    def _log_assessment(self, assessment: dict):
        with open(HISTORY_FILE, "a") as f:
            f.write(json.dumps(assessment) + "\n")

    def get_verbosity_options(self) -> dict:
        return VERBOSITY_LEVELS

    def get_state(self) -> dict:
        return self._state

    def get_stats(self) -> dict:
        if not HISTORY_FILE.exists():
            return {"total_assessments": 0}
        lines = [l for l in HISTORY_FILE.read_text().split("\n") if l.strip()]
        assessments = [json.loads(l) for l in lines]
        distribution = {}
        for a in assessments:
            level = a.get("load_level", "unknown")
            distribution[level] = distribution.get(level, 0) + 1
        return {
            "total_assessments": len(assessments),
            "load_distribution": distribution,
            "current_state": self._state,
        }


_cognitive: Optional[ReasoningCognitiveLoadSkill] = None

def get_cognitive() -> ReasoningCognitiveLoadSkill:
    global _cognitive
    if _cognitive is None:
        _cognitive = ReasoningCognitiveLoadSkill()
    return _cognitive
