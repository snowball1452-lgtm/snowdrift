"""
Calendar Cleric — Focus block defender + meeting rescheduler
Defends your deep work time. Reschedules low-priority meetings with a polite, on-brand note.
"""

import os
import json
import hashlib
import httpx
from datetime import datetime, timezone
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Optional

CLERIC_DIR = Path(".calendar_cleric")
EVENTS_FILE = CLERIC_DIR / "events.jsonl"
FOCUS_BLOCKS = CLERIC_DIR / "focus_blocks.json"
DECISIONS_LOG = CLERIC_DIR / "decisions.jsonl"

API_KEY = os.environ.get("GROQ_API_KEY") or os.environ.get("EMERGENT_LLM_KEY", "")
API_BASE = os.environ.get("SWARM_API_BASE", "https://api.groq.com/openai/v1")
MODEL = os.environ.get("SWARM_MODEL", "llama-3.3-70b-versatile")


@dataclass
class MeetingDecision:
    event_id: str
    title: str
    attendees: list[str]
    proposed_time: str
    priority: str
    score: float
    decision: str
    reschedule_note: Optional[str]
    suggested_slot: Optional[str]
    decided_at: str


class CalendarClericSkill:
    def __init__(self):
        CLERIC_DIR.mkdir(parents=True, exist_ok=True)
        if not FOCUS_BLOCKS.exists():
            FOCUS_BLOCKS.write_text(json.dumps({
                "blocks": [
                    {"label": "Morning Deep Work", "days": ["Mon", "Tue", "Wed", "Thu", "Fri"], "start": "09:00", "end": "12:00"},
                    {"label": "Afternoon Focus", "days": ["Mon", "Wed", "Fri"], "start": "14:00", "end": "16:00"},
                ],
                "min_notice_hours": 24,
                "max_meetings_per_day": 3,
            }, indent=2))

    async def _llm(self, prompt: str) -> str:
        if not API_KEY:
            return ""
        try:
            async with httpx.AsyncClient(timeout=20) as client:
                r = await client.post(
                    f"{API_BASE}/chat/completions",
                    headers={"Authorization": f"Bearer {API_KEY}"},
                    json={"model": MODEL, "messages": [{"role": "user", "content": prompt}], "max_tokens": 500},
                )
                return r.json()["choices"][0]["message"]["content"].strip()
        except Exception:
            return ""

    def get_focus_blocks(self) -> dict:
        return json.loads(FOCUS_BLOCKS.read_text())

    def set_focus_blocks(self, blocks: dict) -> dict:
        FOCUS_BLOCKS.write_text(json.dumps(blocks, indent=2))
        return blocks

    async def evaluate_meeting(self, title: str, attendees: list[str], proposed_time: str,
                                duration_min: int = 30, description: str = "") -> MeetingDecision:
        focus = self.get_focus_blocks()
        event_id = hashlib.sha256(f"{title}:{proposed_time}".encode()).hexdigest()[:12]
        prompt = f"""You are Calendar Cleric, a focus-block defender. Evaluate this meeting request.

Meeting: {title}
Time: {proposed_time} ({duration_min} min)
Attendees: {', '.join(attendees) if attendees else 'unknown'}
Description: {description or 'none'}

Focus blocks (PROTECT THESE):
{json.dumps(focus['blocks'], indent=2)}

Max meetings/day: {focus.get('max_meetings_per_day', 3)}
Min notice required: {focus.get('min_notice_hours', 24)}h

Respond in JSON only (no markdown):
{{
  "priority": "<critical|high|medium|low|spam>",
  "score": <0.0-1.0, where 1.0 = must-attend>,
  "decision": "<keep|reschedule|decline>",
  "reasoning": "<one sentence>",
  "reschedule_note": "<polite, professional note to send if rescheduling, or null>",
  "suggested_slot": "<suggested alternative time slot like 'Tue 2pm-3pm', or null>"
}}"""
        raw = await self._llm(prompt)
        try:
            data = json.loads(raw)
        except Exception:
            data = {"priority": "medium", "score": 0.5, "decision": "keep",
                    "reasoning": "Could not evaluate", "reschedule_note": None, "suggested_slot": None}

        decision = MeetingDecision(
            event_id=event_id,
            title=title,
            attendees=attendees,
            proposed_time=proposed_time,
            priority=data.get("priority", "medium"),
            score=float(data.get("score", 0.5)),
            decision=data.get("decision", "keep"),
            reschedule_note=data.get("reschedule_note"),
            suggested_slot=data.get("suggested_slot"),
            decided_at=datetime.now(timezone.utc).isoformat(),
        )
        with open(DECISIONS_LOG, "a") as f:
            f.write(json.dumps(asdict(decision)) + "\n")
        return decision

    async def generate_reschedule_note(self, meeting_title: str, requester: str, reason: str = "") -> str:
        prompt = f"""Write a brief, professional, warm reschedule note for a meeting request.

Meeting: {meeting_title}
Requester: {requester}
Reason: {reason or 'schedule conflict with existing commitments'}

Write only the message body (2-3 sentences max). Sound like a real person, not a corporate bot."""
        return await self._llm(prompt) or f"Hi {requester}, I'd love to connect but I have a conflict at that time. Could we find something later in the week?"

    def get_decisions(self, limit: int = 20) -> list[dict]:
        if not DECISIONS_LOG.exists():
            return []
        lines = [l for l in DECISIONS_LOG.read_text().split("\n") if l.strip()]
        return [json.loads(l) for l in lines[-limit:]]

    def get_stats(self) -> dict:
        decisions = self.get_decisions(100)
        return {
            "total_evaluated": len(decisions),
            "kept": len([d for d in decisions if d.get("decision") == "keep"]),
            "rescheduled": len([d for d in decisions if d.get("decision") == "reschedule"]),
            "declined": len([d for d in decisions if d.get("decision") == "decline"]),
            "focus_hours_defended": len([d for d in decisions if d.get("decision") in ["reschedule", "decline"]]) * 0.5,
            "focus_blocks": self.get_focus_blocks(),
        }


_cleric: Optional[CalendarClericSkill] = None

def get_cleric() -> CalendarClericSkill:
    global _cleric
    if _cleric is None:
        _cleric = CalendarClericSkill()
    return _cleric
