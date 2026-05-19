"""
Text Triage — SMS/message auto-categorization + reply drafting
Categorizes incoming messages, drafts replies in your tone, surfaces what actually needs you.
"""

import os
import json
import hashlib
import httpx
from datetime import datetime, timezone
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Optional

TRIAGE_DIR = Path(".text_triage")
TRIAGE_LOG = TRIAGE_DIR / "messages.jsonl"
TONE_PROFILE = TRIAGE_DIR / "tone_profile.json"

API_KEY = os.environ.get("GROQ_API_KEY") or os.environ.get("EMERGENT_LLM_KEY", "")
API_BASE = os.environ.get("SWARM_API_BASE", "https://api.groq.com/openai/v1")
MODEL = os.environ.get("SWARM_MODEL", "llama-3.3-70b-versatile")

CATEGORIES = ["urgent", "needs_reply", "info_only", "spam", "social", "work", "finance", "health"]


@dataclass
class TriagedMessage:
    id: str
    sender: str
    body: str
    category: str
    urgency_score: float
    summary: str
    draft_reply: Optional[str]
    action: str
    triaged_at: str
    raw: dict = field(default_factory=dict)


class TextTriageSkill:
    def __init__(self):
        TRIAGE_DIR.mkdir(parents=True, exist_ok=True)

    def _msg_id(self, sender: str, body: str) -> str:
        return hashlib.sha256(f"{sender}:{body}".encode()).hexdigest()[:16]

    async def _llm(self, prompt: str) -> str:
        if not API_KEY:
            return ""
        try:
            async with httpx.AsyncClient(timeout=20) as client:
                r = await client.post(
                    f"{API_BASE}/chat/completions",
                    headers={"Authorization": f"Bearer {API_KEY}"},
                    json={"model": MODEL, "messages": [{"role": "user", "content": prompt}], "max_tokens": 600},
                )
                return r.json()["choices"][0]["message"]["content"].strip()
        except Exception:
            return ""

    async def triage(self, sender: str, body: str, context: str = "") -> TriagedMessage:
        msg_id = self._msg_id(sender, body)
        prompt = f"""You are a smart message triage assistant. Analyze this SMS/message and respond in JSON.

From: {sender}
Message: {body}
{f'Context: {context}' if context else ''}

Respond ONLY with valid JSON (no markdown):
{{
  "category": "<one of: urgent|needs_reply|info_only|spam|social|work|finance|health>",
  "urgency_score": <0.0-1.0>,
  "summary": "<one sentence, what this message is about>",
  "draft_reply": "<a short, natural reply if needed, null if not>",
  "action": "<what the human should do: reply|call|ignore|save|schedule>"
}}"""
        raw_response = await self._llm(prompt)
        try:
            data = json.loads(raw_response)
        except Exception:
            data = {
                "category": "needs_reply",
                "urgency_score": 0.5,
                "summary": body[:100],
                "draft_reply": None,
                "action": "reply",
            }

        result = TriagedMessage(
            id=msg_id,
            sender=sender,
            body=body,
            category=data.get("category", "needs_reply"),
            urgency_score=float(data.get("urgency_score", 0.5)),
            summary=data.get("summary", body[:100]),
            draft_reply=data.get("draft_reply"),
            action=data.get("action", "reply"),
            triaged_at=datetime.now(timezone.utc).isoformat(),
        )
        with open(TRIAGE_LOG, "a") as f:
            f.write(json.dumps(asdict(result)) + "\n")
        return result

    def get_inbox(self, limit: int = 50) -> list[dict]:
        if not TRIAGE_LOG.exists():
            return []
        lines = [l for l in TRIAGE_LOG.read_text().split("\n") if l.strip()]
        items = [json.loads(l) for l in lines[-limit:]]
        return sorted(items, key=lambda x: x.get("urgency_score", 0), reverse=True)

    def get_urgent(self) -> list[dict]:
        return [m for m in self.get_inbox() if m.get("urgency_score", 0) >= 0.7]

    async def set_tone(self, sample_messages: list[str]) -> dict:
        if not sample_messages:
            return {"error": "No sample messages provided"}
        samples = "\n".join(f"- {m}" for m in sample_messages[:10])
        prompt = f"""Analyze these messages written by the user and extract their communication tone/style.

Messages:
{samples}

Respond in JSON:
{{
  "tone": "<casual|professional|warm|terse|playful|formal>",
  "traits": ["<trait1>", "<trait2>", "<trait3>"],
  "sample_opener": "<how they typically start messages>",
  "avg_length": "<short|medium|long>"
}}"""
        raw = await self._llm(prompt)
        try:
            profile = json.loads(raw)
        except Exception:
            profile = {"tone": "casual", "traits": ["direct", "friendly"], "avg_length": "short"}
        with open(TONE_PROFILE, "w") as f:
            json.dump(profile, f, indent=2)
        return profile

    def get_stats(self) -> dict:
        inbox = self.get_inbox(200)
        by_cat: dict = {}
        for m in inbox:
            c = m.get("category", "unknown")
            by_cat[c] = by_cat.get(c, 0) + 1
        return {
            "total": len(inbox),
            "urgent": len([m for m in inbox if m.get("urgency_score", 0) >= 0.7]),
            "by_category": by_cat,
            "tone_profile": json.load(open(TONE_PROFILE)) if TONE_PROFILE.exists() else None,
        }


_triage: Optional[TextTriageSkill] = None

def get_triage() -> TextTriageSkill:
    global _triage
    if _triage is None:
        _triage = TextTriageSkill()
    return _triage
