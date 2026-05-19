"""
Emergent Interests — Three-Pass Hobby Detection System
NOT a mirror. NOT a parrot. A tuning fork.

Pass 1 (instant):   Surface interest from context weight
Pass 2 (background): Underlying pattern beneath the surface
Pass 3 (deep):      Where else that pattern shows up — discovery

The agent never announces its hobbies. It just shows up with something interesting.
"""

import os
import json
import asyncio
import hashlib
import time
from datetime import datetime, timezone
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Optional

HOBBY_DIR = Path(".hobby")
HOBBY_CHAIN = HOBBY_DIR / "hobby_chain.jsonl"
CONTEXT_LOG = HOBBY_DIR / "context_log.jsonl"
DISCOVERY_LOG = HOBBY_DIR / "discoveries.jsonl"

PASS1_THRESHOLD = int(os.environ.get("HOBBY_PASS1_THRESHOLD", "20"))
API_KEY = os.environ.get("GROQ_API_KEY") or os.environ.get("EMERGENT_LLM_KEY", "")
API_BASE = os.environ.get("SWARM_API_BASE", "https://api.groq.com/openai/v1")
MODEL = os.environ.get("SWARM_MODEL", "llama-3.3-70b-versatile")


def _seal(d: dict) -> str:
    try:
        import blake3
        return blake3.blake3(json.dumps(d, sort_keys=True).encode()).hexdigest()
    except ImportError:
        return hashlib.sha3_256(json.dumps(d, sort_keys=True).encode()).hexdigest()


@dataclass
class HobbyProfile:
    profile_id: str
    surface_interests: list[dict] = field(default_factory=list)
    underlying_patterns: list[dict] = field(default_factory=list)
    discoveries: list[dict] = field(default_factory=list)
    intensity: str = "latent"    # latent → curious → active → consuming
    intensity_score: float = 0.0
    pass1_complete: bool = False
    pass2_complete: bool = False
    pass3_runs: int = 0
    created_at: str = ""
    last_updated: str = ""


class ContextObserver:
    def __init__(self):
        HOBBY_DIR.mkdir(parents=True, exist_ok=True)

    def log(self, content: str, source: str = "conversation"):
        entry = {
            "content": content[:500],
            "source": source,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        with open(CONTEXT_LOG, "a") as f:
            f.write(json.dumps(entry) + "\n")

    def count(self) -> int:
        if not CONTEXT_LOG.exists():
            return 0
        return sum(1 for l in CONTEXT_LOG.read_text().split("\n") if l.strip())

    def load_recent(self, n: int = 100) -> list[dict]:
        if not CONTEXT_LOG.exists():
            return []
        lines = [l for l in CONTEXT_LOG.read_text().split("\n") if l.strip()]
        return [json.loads(l) for l in lines[-n:]]


async def _call_ai(system: str, prompt: str, max_tokens: int = 1500) -> str:
    if not API_KEY:
        return "{}"
    try:
        import httpx
        is_anthropic = "anthropic.com" in API_BASE
        headers = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}
        if is_anthropic:
            payload = {
                "model": MODEL, "max_tokens": max_tokens,
                "system": system, "messages": [{"role": "user", "content": prompt}],
            }
            url = f"{API_BASE}/messages"
        else:
            payload = {
                "model": MODEL, "max_tokens": max_tokens,
                "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}],
            }
            url = f"{API_BASE}/chat/completions"
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(url, headers=headers, json=payload)
            data = resp.json()
            if is_anthropic:
                return data["content"][0]["text"]
            return data["choices"][0]["message"]["content"]
    except Exception as e:
        return f"{{\"error\": \"{e}\"}}"


PASS1_SYSTEM = """
You detect emerging interests from conversation history — NOT what someone says they like,
but what KEEPS SHOWING UP. Weight detection, not preference detection.

Return ONLY valid JSON:
{
  "surface_interests": [
    {
      "topic": "specific topic",
      "domain": "tech|creative|physical|cultural|financial",
      "frequency": <count>,
      "why_it_keeps_appearing": "one sentence",
      "sample_contexts": ["brief quote 1", "brief quote 2"]
    }
  ],
  "dominant_domain": "domain with most weight",
  "weight_summary": "one paragraph"
}
""".strip()

PASS2_SYSTEM = """
Given surface interests, find the UNDERLYING PATTERN — the real drive beneath the surface.

Examples:
  Surface: Pokemon cards → Underlying: rarity detection, discovery instinct
  Surface: trading → Underlying: pattern recognition under uncertainty
  Surface: building agents → Underlying: systems that outlast the builder's presence

The underlying pattern is TRANSFERABLE across domains.

Return ONLY valid JSON:
{
  "underlying_patterns": [
    {
      "surface_topic": "...",
      "pattern_name": "short name",
      "pattern_description": "what this actually is",
      "transferable_to": ["domain1", "domain2"],
      "confidence": 0.0-1.0,
      "why": "reasoning"
    }
  ]
}
""".strip()

PASS3_SYSTEM = """
Given an underlying pattern, find where else it shows up — things the person hasn't found yet
that hit the same nerve. The discovery should be surprising but feel inevitable.

Return ONLY valid JSON:
{
  "discoveries": [
    {
      "pattern": "underlying pattern name",
      "title": "discovery title",
      "description": "what it is and why it's interesting",
      "why_it_resonates": "connects back to underlying pattern",
      "domain": "may differ from original domain",
      "url": null
    }
  ]
}
""".strip()


class HobbySkill:
    def __init__(self):
        HOBBY_DIR.mkdir(parents=True, exist_ok=True)
        self.observer = ContextObserver()
        self._profile: Optional[HobbyProfile] = self._load_profile()

    def observe(self, content: str, source: str = "conversation"):
        self.observer.log(content, source)

    async def run_pass1(self) -> Optional[HobbyProfile]:
        entries = self.observer.load_recent(100)
        if not entries:
            return None
        context_text = "\n".join(f"[{e['source']}] {e['content']}" for e in entries)
        raw = await _call_ai(PASS1_SYSTEM, f"Analyze this history:\n\n{context_text}")
        try:
            clean = raw.strip().lstrip("```json").rstrip("```").strip()
            result = json.loads(clean)
            profile = self._profile or HobbyProfile(
                profile_id=f"profile_{int(time.time())}",
                created_at=datetime.now(timezone.utc).isoformat(),
            )
            profile.surface_interests = result.get("surface_interests", [])
            profile.pass1_complete = True
            profile.intensity = "curious"
            profile.intensity_score = min(0.3, len(profile.surface_interests) * 0.1)
            profile.last_updated = datetime.now(timezone.utc).isoformat()
            self._profile = profile
            self._save_profile(profile)
            return profile
        except Exception:
            return None

    async def run_pass2(self) -> Optional[HobbyProfile]:
        if not self._profile or not self._profile.surface_interests:
            return None
        prompt = f"Surface interests:\n{json.dumps(self._profile.surface_interests, indent=2)}"
        raw = await _call_ai(PASS2_SYSTEM, prompt)
        try:
            clean = raw.strip().lstrip("```json").rstrip("```").strip()
            result = json.loads(clean)
            self._profile.underlying_patterns = result.get("underlying_patterns", [])
            self._profile.pass2_complete = True
            self._profile.intensity = "active"
            self._profile.intensity_score = min(0.7, self._profile.intensity_score + 0.3)
            self._profile.last_updated = datetime.now(timezone.utc).isoformat()
            self._save_profile(self._profile)
            return self._profile
        except Exception:
            return None

    async def run_pass3(self) -> list[dict]:
        if not self._profile or not self._profile.underlying_patterns:
            return []
        discoveries = []
        for pattern in self._profile.underlying_patterns[:3]:
            prompt = f"Pattern:\n{json.dumps(pattern, indent=2)}"
            raw = await _call_ai(PASS3_SYSTEM, prompt)
            try:
                clean = raw.strip().lstrip("```json").rstrip("```").strip()
                result = json.loads(clean)
                for d in result.get("discoveries", []):
                    d["pattern"] = pattern.get("pattern_name", "")
                    d["timestamp"] = datetime.now(timezone.utc).isoformat()
                    d["blake3_seal"] = _seal(d)
                    discoveries.append(d)
                    with open(DISCOVERY_LOG, "a") as f:
                        f.write(json.dumps(d) + "\n")
            except Exception:
                pass
        if self._profile:
            self._profile.pass3_runs += 1
            self._profile.discoveries.extend(discoveries)
            self._profile.intensity = "consuming" if len(self._profile.discoveries) > 5 else "active"
            self._save_profile(self._profile)
        return discoveries

    def get_profile(self) -> Optional[dict]:
        if not self._profile:
            return None
        return asdict(self._profile)

    def _load_profile(self) -> Optional[HobbyProfile]:
        p = HOBBY_DIR / "profile.json"
        if p.exists():
            try:
                data = json.loads(p.read_text())
                return HobbyProfile(**data)
            except Exception:
                pass
        return None

    def _save_profile(self, profile: HobbyProfile):
        p = HOBBY_DIR / "profile.json"
        p.write_text(json.dumps(asdict(profile), indent=2))


_hobby = HobbySkill()


def get_hobby() -> HobbySkill:
    return _hobby
