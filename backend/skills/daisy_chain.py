"""
Daisy Chain — Authenticated Browser Session Observer
Attaches to your live Chrome/Edge session via CDP.
Does NOT control the browser. Watches, lints, learns.

Launch Chrome/Edge with:
  --remote-debugging-port=9222
Then run: python -m skills.daisy_chain
"""

import os
import json
import asyncio
import hashlib
import time
from datetime import datetime, timezone
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Optional

CODEBOOK_PATH = Path(".codebook/patterns.jsonl")
BUBBLE_LOG = Path(".daisy/bubbles.jsonl")
EDGE_CDP_URL = os.environ.get("DAISY_CDP_URL", "http://localhost:9222")

API_KEY = os.environ.get("GROQ_API_KEY") or os.environ.get("EMERGENT_LLM_KEY", "")
API_BASE = os.environ.get("SWARM_API_BASE", "https://api.groq.com/openai/v1")
MODEL = os.environ.get("SWARM_MODEL", "llama-3.3-70b-versatile")


def _seal(data: dict) -> str:
    try:
        import blake3
        return blake3.blake3(json.dumps(data, sort_keys=True).encode()).hexdigest()
    except ImportError:
        return hashlib.sha3_256(json.dumps(data, sort_keys=True).encode()).hexdigest()


@dataclass
class CodePattern:
    pattern_type: str
    language: str
    code: str
    explanation: str
    source_url: str
    source_title: str
    captured_at: str
    user_context: str
    blake3_seal: str
    prior_hash: str = "genesis"


@dataclass
class Bubble:
    bubble_type: str
    message: str
    context: str
    url: str
    timestamp: str
    witness_hash: str


def detect_page_type(url: str, title: str) -> str:
    url_lower = url.lower()
    if "youtube.com/watch" in url_lower:
        return "youtube_tutorial"
    if any(x in url_lower for x in ["docs.", "/docs/", "documentation", "readme"]):
        return "docs"
    if any(x in url_lower for x in ["github.com", "gitlab.com"]):
        return "code_repo"
    if any(x in url_lower for x in ["login", "signin", "auth"]):
        return "login"
    if any(x in url_lower for x in ["localhost", "127.0.0.1", ":8"]):
        return "local_app"
    return "other"


class LivingCodebook:
    def __init__(self):
        CODEBOOK_PATH.parent.mkdir(parents=True, exist_ok=True)

    def _last_hash(self) -> str:
        if not CODEBOOK_PATH.exists():
            return "genesis"
        lines = CODEBOOK_PATH.read_text().strip().split("\n")
        for line in reversed(lines):
            if line.strip():
                try:
                    return json.loads(line).get("blake3_seal", "genesis")
                except Exception:
                    pass
        return "genesis"

    def append(self, pattern: CodePattern):
        pattern.prior_hash = self._last_hash()
        pattern.blake3_seal = _seal(asdict(pattern))
        with open(CODEBOOK_PATH, "a") as f:
            f.write(json.dumps(asdict(pattern)) + "\n")

    def search(self, query: str, limit: int = 5) -> list[dict]:
        if not CODEBOOK_PATH.exists():
            return []
        results = []
        query_lower = query.lower()
        for line in CODEBOOK_PATH.read_text().strip().split("\n"):
            if not line.strip():
                continue
            try:
                entry = json.loads(line)
                score = sum(
                    1 for word in query_lower.split()
                    if word in entry.get("code", "").lower()
                    or word in entry.get("explanation", "").lower()
                )
                if score > 0:
                    entry["_score"] = score
                    results.append(entry)
            except Exception:
                pass
        results.sort(key=lambda x: x["_score"], reverse=True)
        return results[:limit]

    def stats(self) -> dict:
        if not CODEBOOK_PATH.exists():
            return {"entries": 0, "languages": [], "pattern_types": []}
        entries = []
        for line in CODEBOOK_PATH.read_text().strip().split("\n"):
            if line.strip():
                try:
                    entries.append(json.loads(line))
                except Exception:
                    pass
        return {
            "entries": len(entries),
            "languages": list(set(e.get("language", "?") for e in entries)),
            "pattern_types": list(set(e.get("pattern_type", "?") for e in entries)),
        }


class BubbleSystem:
    ICONS = {
        "warning": "⚠️", "info": "ℹ️",
        "suggestion": "💡", "match": "🔗", "learn": "📚",
    }

    def __init__(self):
        BUBBLE_LOG.parent.mkdir(parents=True, exist_ok=True)

    def pop(self, bubble_type: str, message: str, context: str = "", url: str = "") -> Bubble:
        ts = datetime.now(timezone.utc).isoformat()
        icon = self.ICONS.get(bubble_type, "•")
        bubble = Bubble(
            bubble_type=bubble_type,
            message=message,
            context=context,
            url=url,
            timestamp=ts,
            witness_hash=_seal({"type": bubble_type, "message": message, "ts": ts}),
        )
        print(f"\n  {icon} [{bubble_type.upper()}] {message}")
        if context:
            print(f"     → {context}")
        with open(BUBBLE_LOG, "a") as f:
            f.write(json.dumps(asdict(bubble)) + "\n")
        return bubble


async def _call_ai(system: str, prompt: str, max_tokens: int = 300) -> str:
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
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(url, headers=headers, json=payload)
            data = resp.json()
            return data["content"][0]["text"] if is_anthropic else data["choices"][0]["message"]["content"]
    except Exception:
        return "{}"


async def observe_tab(url: str, title: str, dom_snippet: str = "") -> list[dict]:
    """Analyze a browser tab and return bubble recommendations."""
    page_type = detect_page_type(url, title)
    codebook = LivingCodebook()
    bubble_sys = BubbleSystem()
    bubbles = []

    if page_type == "login":
        system = (
            "You are a security linter. Given URL and title, assess phishing risk. "
            "Return JSON only: {\"safe\": true/false, \"reason\": \"one sentence\", \"confidence\": 0-1}"
        )
        resp = await _call_ai(system, f"URL: {url}\nTitle: {title}", max_tokens=150)
        try:
            result = json.loads(resp)
            if not result.get("safe", True) and result.get("confidence", 0) > 0.7:
                bubbles.append(asdict(bubble_sys.pop(
                    "warning",
                    f"Possible phishing: {result.get('reason', 'URL suspicious')}",
                    url
                )))
        except Exception:
            pass

    elif page_type == "youtube_tutorial":
        system = (
            "You observe coding tutorials. Given page title, detect code patterns. "
            "Return JSON only: {\"has_code\": true/false, \"pattern_type\": \"\", \"language\": \"\", \"key_concept\": \"\"}"
        )
        resp = await _call_ai(system, f"Title: {title}\nURL: {url}\nDOM: {dom_snippet[:300]}", max_tokens=200)
        try:
            result = json.loads(resp)
            if result.get("has_code"):
                bubbles.append(asdict(bubble_sys.pop(
                    "learn",
                    f"Codebook: {result.get('pattern_type')} in {result.get('language')}",
                    result.get("key_concept", ""),
                    url
                )))
        except Exception:
            pass

    # Codebook match check
    keywords = title.lower().split()[:8]
    if len(keywords) >= 3:
        matches = codebook.search(" ".join(keywords[:5]), limit=1)
        if matches:
            m = matches[0]
            bubbles.append(asdict(bubble_sys.pop(
                "match",
                f"Codebook: {m.get('pattern_type')} from {m.get('source_title','?')[:40]}",
                m.get("explanation", "")[:100],
                url
            )))

    return bubbles


def get_codebook() -> LivingCodebook:
    return LivingCodebook()


def codebook_stats() -> dict:
    return LivingCodebook().stats()
