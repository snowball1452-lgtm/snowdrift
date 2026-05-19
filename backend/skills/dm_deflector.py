"""
DM Deflector — Filters Instagram + LinkedIn DMs.
Real humans get through. Pitch decks don't.
"""

import os
import json
import hashlib
import httpx
from datetime import datetime, timezone
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Optional

DEFLECTOR_DIR = Path(".dm_deflector")
DMS_FILE = DEFLECTOR_DIR / "dms.jsonl"
ALLOWLIST_FILE = DEFLECTOR_DIR / "allowlist.json"
BLOCKLIST_FILE = DEFLECTOR_DIR / "blocklist.json"

API_KEY = os.environ.get("GROQ_API_KEY") or os.environ.get("EMERGENT_LLM_KEY", "")
API_BASE = os.environ.get("SWARM_API_BASE", "https://api.groq.com/openai/v1")
MODEL = os.environ.get("SWARM_MODEL", "llama-3.3-70b-versatile")

DM_TYPES = ["real_human", "pitch", "spam", "recruiter", "collab_legit",
            "collab_spam", "fan", "bot", "cold_outreach", "press"]


@dataclass
class DMVerdict:
    dm_id: str
    platform: str
    sender: str
    sender_follower_count: Optional[int]
    message_preview: str
    dm_type: str
    spam_score: float
    verdict: str
    reason: str
    auto_response: Optional[str]
    deflected: bool
    processed_at: str


class DMDeflectorSkill:
    def __init__(self):
        DEFLECTOR_DIR.mkdir(parents=True, exist_ok=True)
        if not ALLOWLIST_FILE.exists():
            ALLOWLIST_FILE.write_text(json.dumps([], indent=2))
        if not BLOCKLIST_FILE.exists():
            BLOCKLIST_FILE.write_text(json.dumps([], indent=2))

    async def _llm(self, prompt: str) -> str:
        if not API_KEY:
            return ""
        try:
            async with httpx.AsyncClient(timeout=20) as client:
                r = await client.post(
                    f"{API_BASE}/chat/completions",
                    headers={"Authorization": f"Bearer {API_KEY}"},
                    json={"model": MODEL, "messages": [{"role": "user", "content": prompt}], "max_tokens": 400},
                )
                return r.json()["choices"][0]["message"]["content"].strip()
        except Exception:
            return ""

    def _get_allowlist(self) -> list[str]:
        return json.loads(ALLOWLIST_FILE.read_text())

    def _get_blocklist(self) -> list[str]:
        return json.loads(BLOCKLIST_FILE.read_text())

    def add_to_allowlist(self, handle: str) -> dict:
        allow = self._get_allowlist()
        if handle not in allow:
            allow.append(handle.lower())
            ALLOWLIST_FILE.write_text(json.dumps(allow, indent=2))
        return {"allowlisted": handle, "total": len(allow)}

    def add_to_blocklist(self, handle: str) -> dict:
        block = self._get_blocklist()
        if handle not in block:
            block.append(handle.lower())
            BLOCKLIST_FILE.write_text(json.dumps(block, indent=2))
        return {"blocklisted": handle, "total": len(block)}

    async def evaluate_dm(self, platform: str, sender: str, message: str,
                           sender_follower_count: Optional[int] = None,
                           sender_bio: str = "") -> DMVerdict:
        dm_id = hashlib.sha256(f"{platform}:{sender}:{message[:100]}".encode()).hexdigest()[:14]

        if sender.lower() in self._get_allowlist():
            verdict_data = {"dm_type": "real_human", "spam_score": 0.0,
                            "verdict": "let_through", "reason": "On your allowlist", "auto_response": None}
        elif sender.lower() in self._get_blocklist():
            verdict_data = {"dm_type": "spam", "spam_score": 1.0,
                            "verdict": "deflect", "reason": "On your blocklist", "auto_response": None}
        else:
            prompt = f"""You are DM Deflector. Classify this {platform} DM.

Sender: {sender}
{f'Follower count: {sender_follower_count:,}' if sender_follower_count else ''}
{f'Bio: {sender_bio}' if sender_bio else ''}
Message: {message[:500]}

Classify this DM and decide if a real human should see it.

Respond in JSON only:
{{
  "dm_type": "<real_human|pitch|spam|recruiter|collab_legit|collab_spam|fan|bot|cold_outreach|press>",
  "spam_score": <0.0-1.0, where 1.0 = definitely spam/pitch>,
  "verdict": "<let_through|deflect|auto_respond>",
  "reason": "<one sentence why>",
  "auto_response": "<polite decline if deflecting, null if letting through>"
}}

Pitches, unsolicited promotions, "partnership opportunities", bots, and cold outreach should be deflected.
Real friends, fans with genuine messages, press from known outlets, and legit collabs should get through."""
            raw = await self._llm(prompt)
            try:
                verdict_data = json.loads(raw)
            except Exception:
                verdict_data = {"dm_type": "unknown", "spam_score": 0.5,
                                "verdict": "let_through", "reason": "Could not classify", "auto_response": None}

        result = DMVerdict(
            dm_id=dm_id, platform=platform, sender=sender,
            sender_follower_count=sender_follower_count,
            message_preview=message[:200],
            dm_type=verdict_data.get("dm_type", "unknown"),
            spam_score=float(verdict_data.get("spam_score", 0.5)),
            verdict=verdict_data.get("verdict", "let_through"),
            reason=verdict_data.get("reason", ""),
            auto_response=verdict_data.get("auto_response"),
            deflected=verdict_data.get("verdict") in ["deflect", "auto_respond"],
            processed_at=datetime.now(timezone.utc).isoformat(),
        )
        with open(DMS_FILE, "a") as f:
            f.write(json.dumps(asdict(result)) + "\n")
        return result

    def get_inbox(self, limit: int = 50, verdict_filter: Optional[str] = None) -> list[dict]:
        if not DMS_FILE.exists():
            return []
        lines = [l for l in DMS_FILE.read_text().split("\n") if l.strip()]
        items = [json.loads(l) for l in lines[-limit:]]
        if verdict_filter:
            items = [i for i in items if i.get("verdict") == verdict_filter]
        return items

    def get_stats(self) -> dict:
        all_dms = self.get_inbox(500)
        return {
            "total_processed": len(all_dms),
            "let_through": len([d for d in all_dms if not d.get("deflected")]),
            "deflected": len([d for d in all_dms if d.get("deflected")]),
            "deflection_rate_pct": round(
                len([d for d in all_dms if d.get("deflected")]) / max(len(all_dms), 1) * 100, 1
            ),
            "by_type": {t: len([d for d in all_dms if d.get("dm_type") == t]) for t in DM_TYPES if
                        any(d.get("dm_type") == t for d in all_dms)},
            "allowlisted": len(self._get_allowlist()),
            "blocklisted": len(self._get_blocklist()),
        }


_deflector: Optional[DMDeflectorSkill] = None

def get_deflector() -> DMDeflectorSkill:
    global _deflector
    if _deflector is None:
        _deflector = DMDeflectorSkill()
    return _deflector
