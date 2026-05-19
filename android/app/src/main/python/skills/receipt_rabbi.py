"""
Receipt Rabbi — Snap a receipt, get it itemized, tagged, and exported.
Vision extraction + line-item parsing + category tagging + spreadsheet export.
"""

import os
import json
import csv
import hashlib
import httpx
import base64
from datetime import datetime, timezone
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Optional

RABBI_DIR = Path(".receipt_rabbi")
RECEIPTS_FILE = RABBI_DIR / "receipts.jsonl"
EXPORT_FILE = RABBI_DIR / "exports"

API_KEY = os.environ.get("GROQ_API_KEY") or os.environ.get("EMERGENT_LLM_KEY", "")
VISION_KEY = os.environ.get("OPENAI_API_KEY") or os.environ.get("EMERGENT_LLM_KEY", "")
API_BASE = os.environ.get("SWARM_API_BASE", "https://api.groq.com/openai/v1")
MODEL = os.environ.get("SWARM_MODEL", "llama-3.3-70b-versatile")

EXPENSE_CATEGORIES = ["food", "transport", "accommodation", "office", "software", "entertainment",
                       "health", "clothing", "groceries", "utilities", "subscriptions", "other"]


@dataclass
class ReceiptItem:
    description: str
    quantity: float
    unit_price: float
    total: float
    category: str


@dataclass
class Receipt:
    receipt_id: str
    merchant: str
    date: str
    total: float
    tax: float
    subtotal: float
    currency: str
    category: str
    items: list[dict]
    raw_text: str
    tags: list[str]
    notes: str
    parsed_at: str
    source: str


class ReceiptRabbiSkill:
    def __init__(self):
        RABBI_DIR.mkdir(parents=True, exist_ok=True)
        (RABBI_DIR / "exports").mkdir(exist_ok=True)

    async def _llm(self, prompt: str) -> str:
        if not API_KEY:
            return ""
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                r = await client.post(
                    f"{API_BASE}/chat/completions",
                    headers={"Authorization": f"Bearer {API_KEY}"},
                    json={"model": MODEL, "messages": [{"role": "user", "content": prompt}], "max_tokens": 800},
                )
                return r.json()["choices"][0]["message"]["content"].strip()
        except Exception:
            return ""

    async def _vision_extract(self, image_b64: str) -> str:
        if not VISION_KEY:
            return ""
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                r = await client.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers={"Authorization": f"Bearer {VISION_KEY}"},
                    json={
                        "model": "gpt-4o-mini",
                        "messages": [{
                            "role": "user",
                            "content": [
                                {"type": "text", "text": "Extract ALL text from this receipt exactly as shown. Include every line item, price, tax, total, merchant name, and date."},
                                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"}},
                            ],
                        }],
                        "max_tokens": 1000,
                    },
                )
                return r.json()["choices"][0]["message"]["content"].strip()
        except Exception:
            return ""

    async def parse_receipt(self, text: str = "", image_b64: str = "", source: str = "manual") -> Receipt:
        if image_b64 and not text:
            text = await self._vision_extract(image_b64)
        if not text:
            text = "Unknown receipt"

        receipt_id = hashlib.sha256(text.encode()).hexdigest()[:16]
        prompt = f"""Parse this receipt and respond in JSON only (no markdown):

Receipt text:
{text[:2000]}

JSON format:
{{
  "merchant": "<store/restaurant name>",
  "date": "<YYYY-MM-DD or best guess>",
  "total": <total amount as number>,
  "tax": <tax amount as number, 0 if not found>,
  "subtotal": <subtotal as number>,
  "currency": "<USD|EUR|GBP|etc>",
  "category": "<one of: {', '.join(EXPENSE_CATEGORIES)}>",
  "items": [
    {{"description": "<item>", "quantity": <num>, "unit_price": <num>, "total": <num>, "category": "<category>"}}
  ],
  "tags": ["<relevant tag>"],
  "notes": "<anything unusual or notable>"
}}"""
        raw = await self._llm(prompt)
        try:
            data = json.loads(raw)
        except Exception:
            data = {
                "merchant": "Unknown", "date": datetime.now().strftime("%Y-%m-%d"),
                "total": 0.0, "tax": 0.0, "subtotal": 0.0, "currency": "USD",
                "category": "other", "items": [], "tags": [], "notes": "",
            }

        receipt = Receipt(
            receipt_id=receipt_id,
            merchant=data.get("merchant", "Unknown"),
            date=data.get("date", datetime.now().strftime("%Y-%m-%d")),
            total=float(data.get("total", 0)),
            tax=float(data.get("tax", 0)),
            subtotal=float(data.get("subtotal", 0)),
            currency=data.get("currency", "USD"),
            category=data.get("category", "other"),
            items=data.get("items", []),
            raw_text=text[:1000],
            tags=data.get("tags", []),
            notes=data.get("notes", ""),
            parsed_at=datetime.now(timezone.utc).isoformat(),
            source=source,
        )
        with open(RECEIPTS_FILE, "a") as f:
            f.write(json.dumps(asdict(receipt)) + "\n")
        return receipt

    def get_receipts(self, limit: int = 50) -> list[dict]:
        if not RECEIPTS_FILE.exists():
            return []
        lines = [l for l in RECEIPTS_FILE.read_text().split("\n") if l.strip()]
        return [json.loads(l) for l in lines[-limit:]]

    def export_csv(self) -> str:
        receipts = self.get_receipts(500)
        path = RABBI_DIR / "exports" / f"receipts_{datetime.now().strftime('%Y%m%d')}.csv"
        with open(path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["receipt_id", "merchant", "date", "total", "tax",
                                                    "subtotal", "currency", "category", "tags", "notes", "parsed_at"])
            writer.writeheader()
            for r in receipts:
                r["tags"] = ", ".join(r.get("tags", []))
                writer.writerow({k: r.get(k, "") for k in writer.fieldnames})
        return str(path)

    def get_stats(self) -> dict:
        receipts = self.get_receipts(500)
        by_cat: dict = {}
        total_spend = 0.0
        for r in receipts:
            c = r.get("category", "other")
            by_cat[c] = by_cat.get(c, 0) + r.get("total", 0)
            total_spend += r.get("total", 0)
        return {
            "total_receipts": len(receipts),
            "total_spend": round(total_spend, 2),
            "by_category": {k: round(v, 2) for k, v in by_cat.items()},
        }


_rabbi: Optional[ReceiptRabbiSkill] = None

def get_rabbi() -> ReceiptRabbiSkill:
    global _rabbi
    if _rabbi is None:
        _rabbi = ReceiptRabbiSkill()
    return _rabbi
