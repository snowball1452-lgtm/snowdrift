"""
Tab Taxidermist — Closes the 84 tabs you swore you'd read.
Saves the gold to a digest. Spares your RAM.
"""

import os
import json
import hashlib
import httpx
from datetime import datetime, timezone, timedelta
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Optional

TAXIDERMIST_DIR = Path(".tab_taxidermist")
TABS_FILE = TAXIDERMIST_DIR / "tabs.jsonl"
DIGESTS_FILE = TAXIDERMIST_DIR / "digests.jsonl"

API_KEY = os.environ.get("GROQ_API_KEY") or os.environ.get("EMERGENT_LLM_KEY", "")
API_BASE = os.environ.get("SWARM_API_BASE", "https://api.groq.com/openai/v1")
MODEL = os.environ.get("SWARM_MODEL", "llama-3.3-70b-versatile")

TAB_CATEGORIES = ["news", "research", "shop", "social", "video", "docs", "tools", "other"]


@dataclass
class SavedTab:
    tab_id: str
    title: str
    url: str
    category: str
    is_gold: bool
    saved_at: str
    digest_included: bool = False


@dataclass
class Digest:
    digest_id: str
    created_at: str
    tab_count: int
    gold_count: int
    categories: dict
    summary: str
    top_items: list[dict]
    ram_saved_mb: float


class TabTaxidermistSkill:
    def __init__(self):
        TAXIDERMIST_DIR.mkdir(parents=True, exist_ok=True)

    async def _llm(self, prompt: str) -> str:
        if not API_KEY:
            return ""
        try:
            async with httpx.AsyncClient(timeout=20) as client:
                r = await client.post(
                    f"{API_BASE}/chat/completions",
                    headers={"Authorization": f"Bearer {API_KEY}"},
                    json={"model": MODEL, "messages": [{"role": "user", "content": prompt}], "max_tokens": 800},
                )
                return r.json()["choices"][0]["message"]["content"].strip()
        except Exception:
            return ""

    async def add_tab(self, title: str, url: str, context: str = "") -> dict:
        tab_id = hashlib.sha256(f"{url}:{datetime.now().isoformat()}".encode()).hexdigest()[:12]
        prompt = f"""Categorize this browser tab into one of: {', '.join(TAB_CATEGORIES)}.

Title: {title}
URL: {url}
{f'Context: {context}' if context else ''}

Is this "gold" (genuinely useful to save)? Answer as JSON:
{{
  "category": "<category>",
  "is_gold": <true or false>,
  "reason": "<one sentence why>"
}}"""
        raw = await self._llm(prompt)
        try:
            data = json.loads(raw)
        except Exception:
            data = {"category": "other", "is_gold": False, "reason": "Could not classify"}

        tab = SavedTab(
            tab_id=tab_id, title=title, url=url,
            category=data.get("category", "other"),
            is_gold=data.get("is_gold", False),
            saved_at=datetime.now(timezone.utc).isoformat(),
        )
        with open(TABS_FILE, "a") as f:
            f.write(json.dumps(asdict(tab)) + "\n")
        return asdict(tab)

    async def batch_add_tabs(self, tabs: list[dict]) -> dict:
        added = []
        for tab in tabs[:100]:
            result = await self.add_tab(tab.get("title", "?"), tab.get("url", ""), tab.get("context", ""))
            added.append(result)
        return {"added": len(added), "tabs": added}

    async def generate_digest(self, days: int = 7, min_gold: int = 5) -> dict:
        if not TABS_FILE.exists():
            return {"error": "No tabs saved yet"}

        lines = [l for l in TABS_FILE.read_text().split("\n") if l.strip()]
        all_tabs = [json.loads(l) for l in lines]
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        recent = [t for t in all_tabs if t.get("saved_at", "") >= cutoff]
        gold_tabs = [t for t in recent if t.get("is_gold")]

        if len(gold_tabs) < min_gold:
            return {"message": f"Not enough gold tabs yet ({len(gold_tabs)}/{min_gold}). Keep collecting."}

        by_cat = {}
        for t in recent:
            c = t.get("category", "other")
            by_cat[c] = by_cat.get(c, 0) + 1

        prompt = f"""Create a short, punchy digest of these saved browser tabs.

Gold tabs ({len(gold_tabs)} worth saving):
{json.dumps(gold_tabs[:20], indent=2)}

Write a 2-3 sentence digest that captures what these tabs are about, then list the top 3 by title."""
        raw = await self._llm(prompt)
        summary = raw or "Mixed research and reads"

        digest = Digest(
            digest_id=hashlib.sha256(json.dumps(gold_tabs).encode()).hexdigest()[:12],
            created_at=datetime.now(timezone.utc).isoformat(),
            tab_count=len(recent), gold_count=len(gold_tabs),
            categories=by_cat, summary=summary,
            top_items=[{"title": t.get("title"), "url": t.get("url")} for t in gold_tabs[:3]],
            ram_saved_mb=round(len(recent) * 0.5, 1),
        )

        with open(DIGESTS_FILE, "a") as f:
            f.write(json.dumps(asdict(digest)) + "\n")

        for t in gold_tabs[:len(gold_tabs)]:
            t["digest_included"] = True

        return asdict(digest)

    def get_open_tabs(self, limit: int = 100) -> list[dict]:
        if not TABS_FILE.exists():
            return []
        lines = [l for l in TABS_FILE.read_text().split("\n") if l.strip()]
        items = [json.loads(l) for l in lines[-limit:]]
        return sorted(items, key=lambda x: x.get("is_gold", False), reverse=True)

    def get_gold_tabs(self) -> list[dict]:
        return [t for t in self.get_open_tabs(500) if t.get("is_gold")]

    def get_digests(self, limit: int = 10) -> list[dict]:
        if not DIGESTS_FILE.exists():
            return []
        lines = [l for l in DIGESTS_FILE.read_text().split("\n") if l.strip()]
        return [json.loads(l) for l in lines[-limit:]]

    def close_tabs(self, tab_ids: list[str]) -> dict:
        if not TABS_FILE.exists():
            return {"closed": 0}
        lines = [l for l in TABS_FILE.read_text().split("\n") if l.strip()]
        all_tabs = [json.loads(l) for l in lines]
        closed_count = len([t for t in all_tabs if t["tab_id"] in tab_ids])
        remaining = [t for t in all_tabs if t["tab_id"] not in tab_ids]
        TABS_FILE.write_text("\n".join(json.dumps(t) for t in remaining) + "\n")
        return {"closed": closed_count, "remaining": len(remaining), "ram_freed_mb": round(closed_count * 0.5, 1)}

    def get_stats(self) -> dict:
        tabs = self.get_open_tabs(500)
        digests = self.get_digests(50)
        return {
            "open_tabs": len(tabs),
            "gold_tabs": len([t for t in tabs if t.get("is_gold")]),
            "by_category": {c: len([t for t in tabs if t.get("category") == c]) for c in TAB_CATEGORIES},
            "digests_created": len(digests),
            "total_ram_saved_mb": round(sum(d.get("ram_saved_mb", 0) for d in digests), 1),
        }


_taxidermist: Optional[TabTaxidermistSkill] = None

def get_taxidermist() -> TabTaxidermistSkill:
    global _taxidermist
    if _taxidermist is None:
        _taxidermist = TabTaxidermistSkill()
    return _taxidermist
