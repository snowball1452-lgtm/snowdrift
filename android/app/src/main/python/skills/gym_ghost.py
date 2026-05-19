"""
Gym Ghost — Logs sets by voice. Builds your next workout from your last one.
Zero typing. Voice-first. Progressive overload by default.
"""

import os
import json
import hashlib
import httpx
from datetime import datetime, timezone, date
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Optional

GHOST_DIR = Path(".gym_ghost")
WORKOUTS_FILE = GHOST_DIR / "workouts.jsonl"
EXERCISES_FILE = GHOST_DIR / "exercises.json"
PR_FILE = GHOST_DIR / "personal_records.json"

API_KEY = os.environ.get("GROQ_API_KEY") or os.environ.get("EMERGENT_LLM_KEY", "")
API_BASE = os.environ.get("SWARM_API_BASE", "https://api.groq.com/openai/v1")
MODEL = os.environ.get("SWARM_MODEL", "llama-3.3-70b-versatile")


@dataclass
class SetLog:
    exercise: str
    sets: int
    reps: int
    weight: float
    unit: str
    rpe: Optional[float]
    notes: str


@dataclass
class WorkoutSession:
    session_id: str
    date: str
    sets: list[dict]
    total_volume: float
    duration_minutes: int
    muscle_groups: list[str]
    notes: str
    logged_at: str


class GymGhostSkill:
    def __init__(self):
        GHOST_DIR.mkdir(parents=True, exist_ok=True)
        if not EXERCISES_FILE.exists():
            EXERCISES_FILE.write_text(json.dumps({}, indent=2))
        if not PR_FILE.exists():
            PR_FILE.write_text(json.dumps({}, indent=2))

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

    async def parse_voice_log(self, voice_text: str) -> list[dict]:
        prompt = f"""Parse this workout voice log into structured set data. People speak naturally — "did three sets of bench, 185 for eight" means 3 sets x 8 reps x 185 lbs.

Voice input: "{voice_text}"

Respond in JSON only — an array of sets:
[
  {{
    "exercise": "<normalized exercise name>",
    "sets": <number of sets>,
    "reps": <reps per set>,
    "weight": <weight as number>,
    "unit": "<lbs|kg|bodyweight>",
    "rpe": <rate of perceived exertion 1-10 or null>,
    "notes": "<any notes like 'paused' or 'close grip'>"
  }}
]

If multiple exercises mentioned, include all of them."""
        raw = await self._llm(prompt)
        try:
            data = json.loads(raw)
            if isinstance(data, list):
                return data
        except Exception:
            pass
        return []

    async def log_session(self, voice_text: str = "", sets: list[dict] = None,
                          duration_minutes: int = 0, notes: str = "") -> WorkoutSession:
        if voice_text and not sets:
            sets = await self.parse_voice_log(voice_text)

        sets = sets or []
        session_id = hashlib.sha256(f"{datetime.now().isoformat()}".encode()).hexdigest()[:12]
        total_volume = sum(s.get("sets", 1) * s.get("reps", 0) * s.get("weight", 0) for s in sets
                           if s.get("unit", "lbs") != "bodyweight")
        muscle_groups = list(set(self._get_muscle_group(s.get("exercise", "")) for s in sets))

        self._update_prs(sets)

        session = WorkoutSession(
            session_id=session_id, date=date.today().isoformat(),
            sets=sets, total_volume=round(total_volume, 1),
            duration_minutes=duration_minutes, muscle_groups=[m for m in muscle_groups if m],
            notes=notes, logged_at=datetime.now(timezone.utc).isoformat(),
        )
        with open(WORKOUTS_FILE, "a") as f:
            f.write(json.dumps(asdict(session)) + "\n")
        return session

    def _get_muscle_group(self, exercise: str) -> str:
        ex = exercise.lower()
        mapping = {
            "chest": ["bench", "push", "fly", "pec", "dip"],
            "back": ["row", "pull", "lat", "deadlift", "chin"],
            "shoulders": ["press", "lateral", "front raise", "shoulder", "ohp"],
            "legs": ["squat", "leg", "lunge", "rdl", "hamstring", "quad", "glute"],
            "arms": ["curl", "tricep", "bicep", "skull", "extension"],
            "core": ["plank", "crunch", "ab", "core", "oblique"],
        }
        for group, keywords in mapping.items():
            if any(k in ex for k in keywords):
                return group
        return ""

    def _update_prs(self, sets: list[dict]):
        prs = json.loads(PR_FILE.read_text())
        for s in sets:
            ex = s.get("exercise", "").lower()
            weight = s.get("weight", 0)
            reps = s.get("reps", 0)
            if not ex or weight <= 0:
                continue
            if ex not in prs or weight > prs[ex].get("weight", 0):
                prs[ex] = {"weight": weight, "reps": reps, "unit": s.get("unit", "lbs"),
                            "date": date.today().isoformat()}
        PR_FILE.write_text(json.dumps(prs, indent=2))

    async def build_next_workout(self) -> dict:
        sessions = self.get_sessions(10)
        if not sessions:
            return {"error": "No workout history yet. Log a session first."}

        last = sessions[-1]
        prompt = f"""You are a smart personal trainer. Build the next workout session based on this history.

Last workout ({last['date']}):
{json.dumps(last['sets'], indent=2)}

Progressive overload rules:
- If last session's top set was below RPE 8: increase weight by 5 lbs (upper) or 10 lbs (lower)
- If at RPE 8-9: keep same weight, add 1 rep
- If RPE 10 or missed reps: keep same weight

Respond in JSON:
{{
  "workout_name": "<catchy name>",
  "estimated_duration_min": <minutes>,
  "sets": [
    {{"exercise": "<name>", "sets": <n>, "target_reps": <n>, "target_weight": <n>, "unit": "lbs|kg", "notes": "<coaching cue>"}}
  ],
  "focus": "<primary muscle groups>",
  "tip": "<one performance tip>"
}}"""
        raw = await self._llm(prompt)
        try:
            return json.loads(raw)
        except Exception:
            return {"error": "Could not build workout.", "last_session": last}

    def get_sessions(self, limit: int = 30) -> list[dict]:
        if not WORKOUTS_FILE.exists():
            return []
        lines = [l for l in WORKOUTS_FILE.read_text().split("\n") if l.strip()]
        return [json.loads(l) for l in lines[-limit:]]

    def get_prs(self) -> dict:
        if not PR_FILE.exists():
            return {}
        return json.loads(PR_FILE.read_text())

    def get_stats(self) -> dict:
        sessions = self.get_sessions(100)
        prs = self.get_prs()
        return {
            "total_sessions": len(sessions),
            "total_prs": len(prs),
            "total_volume_lbs": round(sum(s.get("total_volume", 0) for s in sessions), 0),
            "most_recent": sessions[-1]["date"] if sessions else None,
            "muscle_groups_trained": list(set(g for s in sessions for g in s.get("muscle_groups", []))),
        }


_ghost: Optional[GymGhostSkill] = None

def get_ghost() -> GymGhostSkill:
    global _ghost
    if _ghost is None:
        _ghost = GymGhostSkill()
    return _ghost
