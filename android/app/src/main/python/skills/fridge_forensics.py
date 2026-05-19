"""
Fridge Forensics — Photo your fridge, get 3 dinner ideas.
Using only what's already in there. No grocery run.
"""

import os
import json
import hashlib
import httpx
from datetime import datetime, timezone
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Optional

FORENSICS_DIR = Path(".fridge_forensics")
INVENTORIES_FILE = FORENSICS_DIR / "inventories.jsonl"
MEALS_FILE = FORENSICS_DIR / "meal_ideas.jsonl"

API_KEY = os.environ.get("GROQ_API_KEY") or os.environ.get("EMERGENT_LLM_KEY", "")
VISION_KEY = os.environ.get("OPENAI_API_KEY") or os.environ.get("EMERGENT_LLM_KEY", "")
API_BASE = os.environ.get("SWARM_API_BASE", "https://api.groq.com/openai/v1")
MODEL = os.environ.get("SWARM_MODEL", "llama-3.3-70b-versatile")


@dataclass
class MealIdea:
    meal_id: str
    fridge_scan_id: str
    meal_name: str
    description: str
    ingredients_used: list[str]
    prep_time_min: int
    difficulty: str
    dietary_flags: list[str]
    recipe_outline: str
    created_at: str


@dataclass
class FridgeScan:
    scan_id: str
    image_b64: Optional[str]
    extracted_items: list[str]
    meal_ideas: int
    analyzed_at: str


class FridgeForensicsSkill:
    def __init__(self):
        FORENSICS_DIR.mkdir(parents=True, exist_ok=True)

    async def _llm(self, prompt: str) -> str:
        if not API_KEY:
            return ""
        try:
            async with httpx.AsyncClient(timeout=20) as client:
                r = await client.post(
                    f"{API_BASE}/chat/completions",
                    headers={"Authorization": f"Bearer {API_KEY}"},
                    json={"model": MODEL, "messages": [{"role": "user", "content": prompt}], "max_tokens": 1000},
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
                                {"type": "text", "text": "List every food item you can see in this fridge photo. Be specific: include quantities where possible (e.g., 'eggs (6)', 'milk (1/2 gallon)')."},
                                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"}},
                            ],
                        }],
                        "max_tokens": 500,
                    },
                )
                return r.json()["choices"][0]["message"]["content"].strip()
        except Exception:
            return ""

    async def analyze_fridge(self, image_b64: str = "", manual_items: list[str] = None) -> dict:
        if manual_items:
            items_text = "\n".join(f"- {item}" for item in manual_items)
        elif image_b64:
            items_text = await self._vision_extract(image_b64)
        else:
            return {"error": "Provide either image_b64 or manual_items"}

        if not items_text:
            return {"error": "Could not extract items from fridge"}

        scan_id = hashlib.sha256(items_text.encode()).hexdigest()[:12]
        prompt = f"""You are a creative chef. Given ONLY these fridge items, brainstorm 3 diverse dinner ideas.
Each should use multiple items from the list (not just one ingredient).

Fridge contents:
{items_text}

For each meal, respond in JSON (array of 3 meals):
[
  {{
    "meal_name": "<catchy name>",
    "description": "<appetizing 1-sentence description>",
    "ingredients_used": ["<item1>", "<item2>"],
    "prep_time_min": <minutes>,
    "difficulty": "<easy|moderate|challenging>",
    "dietary_flags": ["<vegetarian|vegan|gluten-free|etc>"],
    "recipe_outline": "<3-4 step bullet outline>"
  }}
]"""
        raw = await self._llm(prompt)
        try:
            meals_data = json.loads(raw)
            if not isinstance(meals_data, list):
                meals_data = [meals_data]
        except Exception:
            meals_data = [
                {
                    "meal_name": "Mixed Plate",
                    "description": "Combine whatever looks good",
                    "ingredients_used": items_text.split("\n")[:3],
                    "prep_time_min": 20,
                    "difficulty": "easy",
                    "dietary_flags": [],
                    "recipe_outline": "1. Prep 2. Cook 3. Enjoy",
                }
            ]

        meal_ideas = []
        for meal in meals_data[:3]:
            m = MealIdea(
                meal_id=hashlib.sha256(f"{scan_id}:{meal.get('meal_name', '')}".encode()).hexdigest()[:12],
                fridge_scan_id=scan_id,
                meal_name=meal.get("meal_name", "?"),
                description=meal.get("description", ""),
                ingredients_used=meal.get("ingredients_used", []),
                prep_time_min=meal.get("prep_time_min", 30),
                difficulty=meal.get("difficulty", "moderate"),
                dietary_flags=meal.get("dietary_flags", []),
                recipe_outline=meal.get("recipe_outline", ""),
                created_at=datetime.now(timezone.utc).isoformat(),
            )
            meal_ideas.append(m)
            with open(MEALS_FILE, "a") as f:
                f.write(json.dumps(asdict(m)) + "\n")

        scan = FridgeScan(
            scan_id=scan_id,
            image_b64=None,
            extracted_items=items_text.split("\n")[:20],
            meal_ideas=len(meal_ideas),
            analyzed_at=datetime.now(timezone.utc).isoformat(),
        )
        with open(INVENTORIES_FILE, "a") as f:
            f.write(json.dumps(asdict(scan)) + "\n")

        return {
            "scan_id": scan_id,
            "items_found": len(scan.extracted_items),
            "meals": [asdict(m) for m in meal_ideas],
        }

    def get_meal_history(self, limit: int = 20) -> list[dict]:
        if not MEALS_FILE.exists():
            return []
        lines = [l for l in MEALS_FILE.read_text().split("\n") if l.strip()]
        return [json.loads(l) for l in lines[-limit:]]

    def get_scans(self, limit: int = 10) -> list[dict]:
        if not INVENTORIES_FILE.exists():
            return []
        lines = [l for l in INVENTORIES_FILE.read_text().split("\n") if l.strip()]
        return [json.loads(l) for l in lines[-limit:]]

    def get_stats(self) -> dict:
        meals = self.get_meal_history(100)
        scans = self.get_scans(50)
        return {
            "total_scans": len(scans),
            "total_meal_ideas": len(meals),
            "avg_meals_per_scan": round(len(meals) / max(len(scans), 1), 1),
            "dietary_categories": list(set(f for m in meals for f in m.get("dietary_flags", []))),
            "difficulty_dist": {
                "easy": len([m for m in meals if m.get("difficulty") == "easy"]),
                "moderate": len([m for m in meals if m.get("difficulty") == "moderate"]),
                "challenging": len([m for m in meals if m.get("difficulty") == "challenging"]),
            },
        }


_forensics: Optional[FridgeForensicsSkill] = None

def get_forensics() -> FridgeForensicsSkill:
    global _forensics
    if _forensics is None:
        _forensics = FridgeForensicsSkill()
    return _forensics
