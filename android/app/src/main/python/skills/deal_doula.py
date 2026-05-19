"""
Deal Doula — Watches prices on things you've half-decided to buy.
Pings only when it's actually a deal — not every price drop.
"""

import os
import json
import hashlib
import httpx
from datetime import datetime, timezone
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Optional

DOULA_DIR = Path(".deal_doula")
WATCHLIST_FILE = DOULA_DIR / "watchlist.json"
PRICE_HISTORY = DOULA_DIR / "price_history.jsonl"
ALERTS_FILE = DOULA_DIR / "alerts.jsonl"

API_KEY = os.environ.get("GROQ_API_KEY") or os.environ.get("EMERGENT_LLM_KEY", "")
API_BASE = os.environ.get("SWARM_API_BASE", "https://api.groq.com/openai/v1")
MODEL = os.environ.get("SWARM_MODEL", "llama-3.3-70b-versatile")


@dataclass
class WatchedItem:
    item_id: str
    name: str
    url: str
    target_price: float
    current_price: float
    original_price: float
    currency: str
    category: str
    notes: str
    added_at: str
    last_checked: str
    deal_threshold_pct: float
    status: str


@dataclass
class DealAlert:
    item_id: str
    item_name: str
    original_price: float
    current_price: float
    savings: float
    savings_pct: float
    deal_score: float
    verdict: str
    reasoning: str
    alerted_at: str


class DealDoulaSkill:
    def __init__(self):
        DOULA_DIR.mkdir(parents=True, exist_ok=True)
        if not WATCHLIST_FILE.exists():
            WATCHLIST_FILE.write_text(json.dumps([], indent=2))

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

    def _get_watchlist(self) -> list[dict]:
        return json.loads(WATCHLIST_FILE.read_text())

    def _save_watchlist(self, items: list[dict]):
        WATCHLIST_FILE.write_text(json.dumps(items, indent=2))

    def add_item(self, name: str, url: str, target_price: float, original_price: float,
                 currency: str = "USD", category: str = "general", notes: str = "",
                 deal_threshold_pct: float = 15.0) -> dict:
        item_id = hashlib.sha256(f"{name}:{url}".encode()).hexdigest()[:12]
        item = WatchedItem(
            item_id=item_id, name=name, url=url,
            target_price=target_price, current_price=original_price,
            original_price=original_price, currency=currency, category=category,
            notes=notes, added_at=datetime.now(timezone.utc).isoformat(),
            last_checked=datetime.now(timezone.utc).isoformat(),
            deal_threshold_pct=deal_threshold_pct, status="watching",
        )
        watchlist = self._get_watchlist()
        watchlist = [w for w in watchlist if w.get("item_id") != item_id]
        watchlist.append(asdict(item))
        self._save_watchlist(watchlist)
        return asdict(item)

    def remove_item(self, item_id: str) -> bool:
        watchlist = self._get_watchlist()
        new = [w for w in watchlist if w.get("item_id") != item_id]
        self._save_watchlist(new)
        return len(new) < len(watchlist)

    async def check_deal(self, item_id: str, current_price: float) -> Optional[DealAlert]:
        watchlist = self._get_watchlist()
        item = next((w for w in watchlist if w.get("item_id") == item_id), None)
        if not item:
            return None

        original = item.get("original_price", current_price)
        savings = original - current_price
        savings_pct = (savings / original * 100) if original > 0 else 0
        threshold = item.get("deal_threshold_pct", 15.0)

        item["current_price"] = current_price
        item["last_checked"] = datetime.now(timezone.utc).isoformat()
        self._save_watchlist([w if w["item_id"] != item_id else item for w in watchlist])

        with open(PRICE_HISTORY, "a") as f:
            f.write(json.dumps({"item_id": item_id, "price": current_price,
                                 "ts": datetime.now(timezone.utc).isoformat()}) + "\n")

        if savings_pct < threshold * 0.5:
            return None

        prompt = f"""Is this a genuinely good deal worth alerting the user about?

Item: {item['name']}
Original price: {original} {item['currency']}
Current price: {current_price} {item['currency']}
Savings: {savings:.2f} ({savings_pct:.1f}%)
Target price they set: {item['target_price']} {item['currency']}
Minimum threshold they want: {threshold}%

Respond in JSON only:
{{
  "deal_score": <0.0-1.0, where 1.0 = incredible deal>,
  "verdict": "<buy_now|wait|decent_deal|not_worth_it>",
  "reasoning": "<one punchy sentence>"
}}"""
        raw = await self._llm(prompt)
        try:
            data = json.loads(raw)
        except Exception:
            data = {"deal_score": savings_pct / 100, "verdict": "decent_deal", "reasoning": f"{savings_pct:.0f}% off"}

        alert = DealAlert(
            item_id=item_id, item_name=item["name"],
            original_price=original, current_price=current_price,
            savings=round(savings, 2), savings_pct=round(savings_pct, 1),
            deal_score=float(data.get("deal_score", 0.5)),
            verdict=data.get("verdict", "decent_deal"),
            reasoning=data.get("reasoning", ""),
            alerted_at=datetime.now(timezone.utc).isoformat(),
        )
        if alert.deal_score >= 0.4:
            with open(ALERTS_FILE, "a") as f:
                f.write(json.dumps(asdict(alert)) + "\n")
            return alert
        return None

    def get_watchlist(self) -> list[dict]:
        return self._get_watchlist()

    def get_alerts(self, limit: int = 20) -> list[dict]:
        if not ALERTS_FILE.exists():
            return []
        lines = [l for l in ALERTS_FILE.read_text().split("\n") if l.strip()]
        return [json.loads(l) for l in lines[-limit:]]

    def get_stats(self) -> dict:
        watchlist = self.get_watchlist()
        alerts = self.get_alerts(100)
        return {
            "watching": len(watchlist),
            "total_alerts": len(alerts),
            "buy_now_alerts": len([a for a in alerts if a.get("verdict") == "buy_now"]),
            "total_savings_flagged": round(sum(a.get("savings", 0) for a in alerts), 2),
        }


_doula: Optional[DealDoulaSkill] = None

def get_doula() -> DealDoulaSkill:
    global _doula
    if _doula is None:
        _doula = DealDoulaSkill()
    return _doula
