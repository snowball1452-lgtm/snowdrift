"""
Reasoning Level 4: Temporal Reasoning
Understands time constraints, deadlines, scheduling, and urgency.
Computes priority scores: (importance × urgency) / time_remaining.
Prevents the agent from treating everything as equal priority.
"""

import re
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Optional

TEMPORAL_DIR = Path(".reasoning_temporal")
TASKS_FILE = TEMPORAL_DIR / "tasks.jsonl"

TIME_PATTERNS = [
    (r"\btoday\b", 0),
    (r"\btonigh?t\b", 0),
    (r"\bthis morning\b", 0),
    (r"\bin (\d+) hours?\b", None),  # dynamic
    (r"\btomorrow\b", 1),
    (r"\bday after tomorrow\b", 2),
    (r"\bthis week\b", 5),
    (r"\bnext week\b", 7),
    (r"\bin (\d+) days?\b", None),  # dynamic
    (r"\bby (\w+ \d+)\b", None),  # date reference
    (r"\bthis month\b", 20),
    (r"\bnext month\b", 30),
    (r"\bno rush\b", 90),
    (r"\beventually\b", 90),
]

IMPORTANCE_SIGNALS = {
    "critical": 1.0,
    "urgent": 0.9,
    "important": 0.8,
    "essential": 0.8,
    "must": 0.85,
    "need to": 0.7,
    "should": 0.5,
    "want to": 0.4,
    "could": 0.3,
    "might": 0.25,
    "whenever": 0.2,
}


@dataclass
class TemporalTask:
    task_id: str
    description: str
    deadline_days: Optional[float]
    urgency_score: float
    importance_score: float
    priority_score: float
    deadline_label: str
    recommendation: str
    created_at: str


class ReasoningTemporalSkill:
    """
    Level 4 Advanced Reasoning: Time-aware task prioritization.
    Knows the difference between "asap" and "whenever".
    Computes actual priority so agent handles things in the right order.
    """

    def __init__(self):
        TEMPORAL_DIR.mkdir(parents=True, exist_ok=True)

    def analyze(self, task: str, context: str = "") -> dict:
        """
        Analyze a task description for temporal constraints.
        Returns: deadline estimate, urgency, importance, priority score.
        """
        import hashlib
        task_id = hashlib.sha256(f"{task}:{datetime.now().isoformat()}".encode()).hexdigest()[:12]

        combined = f"{task} {context}".lower()

        # Extract deadline
        deadline_days, deadline_label = self._extract_deadline(combined)

        # Extract importance
        importance = self._extract_importance(combined)

        # Compute urgency from deadline
        if deadline_days is None:
            urgency = 0.3  # unknown deadline = low default urgency
            deadline_label = "no deadline detected"
        elif deadline_days <= 0:
            urgency = 1.0
        elif deadline_days <= 1:
            urgency = 0.95
        elif deadline_days <= 3:
            urgency = 0.8
        elif deadline_days <= 7:
            urgency = 0.6
        elif deadline_days <= 14:
            urgency = 0.45
        elif deadline_days <= 30:
            urgency = 0.3
        else:
            urgency = 0.15

        # Priority = (importance × urgency) / log(deadline + 1)
        import math
        time_factor = math.log(max(deadline_days or 1, 1) + 1)
        priority = (importance * urgency) / time_factor if time_factor else importance * urgency
        priority = round(min(priority, 1.0), 3)

        # Recommendation
        recommendation = self._recommend(priority, deadline_days, urgency)

        result = TemporalTask(
            task_id=task_id,
            description=task[:100],
            deadline_days=deadline_days,
            urgency_score=round(urgency, 2),
            importance_score=round(importance, 2),
            priority_score=priority,
            deadline_label=deadline_label,
            recommendation=recommendation,
            created_at=datetime.now(timezone.utc).isoformat(),
        )

        self._log(asdict(result))
        return asdict(result)

    def rank_tasks(self, tasks: list[str]) -> list[dict]:
        """Rank multiple tasks by priority score. Highest first."""
        analyzed = [self.analyze(t) for t in tasks]
        return sorted(analyzed, key=lambda x: x["priority_score"], reverse=True)

    def _extract_deadline(self, text: str) -> tuple[Optional[float], str]:
        """Extract deadline in days from text."""
        # Dynamic patterns first
        hours_match = re.search(r"in (\d+) hours?", text)
        if hours_match:
            h = int(hours_match.group(1))
            return round(h / 24, 2), f"in {h} hours"

        days_match = re.search(r"in (\d+) days?", text)
        if days_match:
            d = int(days_match.group(1))
            return float(d), f"in {d} days"

        weeks_match = re.search(r"in (\d+) weeks?", text)
        if weeks_match:
            w = int(weeks_match.group(1))
            return float(w * 7), f"in {w} weeks"

        # Static patterns
        for pattern, days in TIME_PATTERNS:
            if days is not None and re.search(pattern, text):
                label = pattern.strip(r"\b").replace("\\", "").strip()
                return float(days), label

        return None, "no deadline"

    def _extract_importance(self, text: str) -> float:
        """Extract importance score from text signals."""
        score = 0.4  # default
        for signal, value in sorted(IMPORTANCE_SIGNALS.items(), key=lambda x: x[1], reverse=True):
            if signal in text:
                score = value
                break
        return score

    def _recommend(self, priority: float, deadline_days: Optional[float], urgency: float) -> str:
        """Generate human-readable recommendation based on computed scores."""
        if priority > 0.8 or urgency >= 0.95:
            return "HANDLE NOW — Critical priority. Drop other tasks."
        elif priority > 0.6:
            return "Handle today — High priority, don't defer."
        elif priority > 0.4:
            return "Schedule this week — Medium priority, needs planning."
        elif priority > 0.2:
            return "Add to backlog — Low priority, handle when available."
        else:
            return "Park it — Very low priority or no deadline pressure."

    def _log(self, task: dict):
        with open(TASKS_FILE, "a") as f:
            f.write(json.dumps(task) + "\n")

    def get_active_tasks(self, limit: int = 50) -> list[dict]:
        if not TASKS_FILE.exists():
            return []
        lines = [l for l in TASKS_FILE.read_text().split("\n") if l.strip()]
        return sorted([json.loads(l) for l in lines[-limit:]], key=lambda x: x.get("priority_score", 0), reverse=True)

    def get_stats(self) -> dict:
        tasks = self.get_active_tasks(100)
        if not tasks:
            return {"total_tasks": 0}
        overdue = [t for t in tasks if (t.get("deadline_days") or 999) <= 0]
        high_prio = [t for t in tasks if t.get("priority_score", 0) > 0.7]
        return {
            "total_tasks": len(tasks),
            "overdue": len(overdue),
            "high_priority": len(high_prio),
            "avg_priority": round(sum(t.get("priority_score", 0) for t in tasks) / len(tasks), 2),
        }


_temporal: Optional[ReasoningTemporalSkill] = None

def get_temporal() -> ReasoningTemporalSkill:
    global _temporal
    if _temporal is None:
        _temporal = ReasoningTemporalSkill()
    return _temporal
