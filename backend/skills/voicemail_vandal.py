"""
Voicemail Vandal — Listens to voicemails so you don't have to.
Transcribes → 1-line summary → urgency score → suggested action.
"""

import os
import json
import hashlib
import httpx
from datetime import datetime, timezone
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Optional

VANDAL_DIR = Path(".voicemail_vandal")
VOICEMAILS_FILE = VANDAL_DIR / "voicemails.jsonl"

API_KEY = os.environ.get("GROQ_API_KEY") or os.environ.get("EMERGENT_LLM_KEY", "")
WHISPER_KEY = os.environ.get("OPENAI_API_KEY") or os.environ.get("EMERGENT_LLM_KEY", "")
API_BASE = os.environ.get("SWARM_API_BASE", "https://api.groq.com/openai/v1")
MODEL = os.environ.get("SWARM_MODEL", "llama-3.3-70b-versatile")

ACTIONS = ["call_back", "reply_sms", "ignore", "save_info", "schedule", "escalate"]


@dataclass
class VoicemailResult:
    vm_id: str
    caller: str
    duration_seconds: int
    transcript: str
    one_liner: str
    urgency_score: float
    action: str
    call_back_by: Optional[str]
    key_info: list[str]
    sentiment: str
    processed_at: str


class VoicemailVandalSkill:
    def __init__(self):
        VANDAL_DIR.mkdir(parents=True, exist_ok=True)

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

    async def _transcribe_audio(self, audio_b64: str) -> str:
        if not WHISPER_KEY or not audio_b64:
            return ""
        try:
            import base64
            audio_bytes = base64.b64decode(audio_b64)
            async with httpx.AsyncClient(timeout=60) as client:
                r = await client.post(
                    "https://api.openai.com/v1/audio/transcriptions",
                    headers={"Authorization": f"Bearer {WHISPER_KEY}"},
                    files={"file": ("voicemail.mp3", audio_bytes, "audio/mpeg")},
                    data={"model": "whisper-1"},
                )
                return r.json().get("text", "")
        except Exception:
            return ""

    async def process(self, caller: str, transcript: str = "", audio_b64: str = "",
                      duration_seconds: int = 0) -> VoicemailResult:
        if audio_b64 and not transcript:
            transcript = await self._transcribe_audio(audio_b64)
        if not transcript:
            transcript = "No transcript available"

        vm_id = hashlib.sha256(f"{caller}:{transcript[:100]}".encode()).hexdigest()[:14]
        prompt = f"""You are Voicemail Vandal. Summarize this voicemail for a busy person.

Caller: {caller}
Duration: {duration_seconds}s
Transcript: {transcript}

Respond in JSON only:
{{
  "one_liner": "<one punchy sentence: who called + what they want>",
  "urgency_score": <0.0-1.0>,
  "action": "<one of: call_back|reply_sms|ignore|save_info|schedule|escalate>",
  "call_back_by": "<time window like 'within 2 hours' or null if not urgent>",
  "key_info": ["<phone number if mentioned>", "<any dates/deadlines>", "<dollar amounts>"],
  "sentiment": "<friendly|neutral|frustrated|urgent|spam>"
}}"""
        raw = await self._llm(prompt)
        try:
            data = json.loads(raw)
        except Exception:
            data = {
                "one_liner": f"{caller} left a voicemail.",
                "urgency_score": 0.3,
                "action": "call_back",
                "call_back_by": None,
                "key_info": [],
                "sentiment": "neutral",
            }

        result = VoicemailResult(
            vm_id=vm_id,
            caller=caller,
            duration_seconds=duration_seconds,
            transcript=transcript,
            one_liner=data.get("one_liner", f"{caller} called."),
            urgency_score=float(data.get("urgency_score", 0.3)),
            action=data.get("action", "call_back"),
            call_back_by=data.get("call_back_by"),
            key_info=[i for i in data.get("key_info", []) if i],
            sentiment=data.get("sentiment", "neutral"),
            processed_at=datetime.now(timezone.utc).isoformat(),
        )
        with open(VOICEMAILS_FILE, "a") as f:
            f.write(json.dumps(asdict(result)) + "\n")
        return result

    def get_inbox(self, limit: int = 30) -> list[dict]:
        if not VOICEMAILS_FILE.exists():
            return []
        lines = [l for l in VOICEMAILS_FILE.read_text().split("\n") if l.strip()]
        items = [json.loads(l) for l in lines[-limit:]]
        return sorted(items, key=lambda x: x.get("urgency_score", 0), reverse=True)

    def get_stats(self) -> dict:
        inbox = self.get_inbox(200)
        return {
            "total": len(inbox),
            "need_callback": len([v for v in inbox if v.get("action") == "call_back"]),
            "ignored": len([v for v in inbox if v.get("action") == "ignore"]),
            "avg_duration": round(sum(v.get("duration_seconds", 0) for v in inbox) / max(len(inbox), 1), 1),
        }


_vandal: Optional[VoicemailVandalSkill] = None

def get_vandal() -> VoicemailVandalSkill:
    global _vandal
    if _vandal is None:
        _vandal = VoicemailVandalSkill()
    return _vandal
