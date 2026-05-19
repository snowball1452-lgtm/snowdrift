"""
GutPunch Async Messaging — Proactive Telegram notifications
Weight accumulates. Threshold crossed. Message fires.
NOT a scheduler. NOT a reminder app. A guillotine.

Three trigger types:
  SCHEDULE  — time-aware warmup before shift end
  TIMED     — deadline detected in content
  GUTPUNCH  — semantic weight threshold crossed
"""

import os
import json
import asyncio
import hashlib
import time
import re
from datetime import datetime, timezone, timedelta
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Optional

MSG_DIR = Path(".async_msg")
WEIGHT_LOG = MSG_DIR / "weight_log.jsonl"
MSG_CHAIN = MSG_DIR / "message_chain.jsonl"

GUTPUNCH_THRESHOLD = float(os.environ.get("GUTPUNCH_THRESHOLD", "0.72"))
SHIFT_END_HOUR = int(os.environ.get("SHIFT_END_HOUR", "17"))
SHIFT_START_HOUR = int(os.environ.get("SHIFT_START_HOUR", "6"))
QUIET_START_HOUR = int(os.environ.get("QUIET_START_HOUR", "22"))
QUIET_END_HOUR = int(os.environ.get("QUIET_END_HOUR", "7"))

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")


def _seal(data: dict) -> str:
    try:
        import blake3
        return blake3.blake3(json.dumps(data, sort_keys=True).encode()).hexdigest()
    except ImportError:
        return hashlib.sha3_256(json.dumps(data, sort_keys=True).encode()).hexdigest()


def _last_chain_hash() -> str:
    if not MSG_CHAIN.exists():
        return "genesis"
    lines = [l for l in MSG_CHAIN.read_text().split("\n") if l.strip()]
    if not lines:
        return "genesis"
    try:
        return json.loads(lines[-1]).get("blake3_seal", "genesis")
    except Exception:
        return "genesis"


# ── Schedule awareness ────────────────────────────────────────────────────────

class ScheduleAwareness:
    def is_quiet_hours(self) -> bool:
        h = datetime.now().hour
        if QUIET_START_HOUR > QUIET_END_HOUR:
            return h >= QUIET_START_HOUR or h < QUIET_END_HOUR
        return QUIET_START_HOUR <= h < QUIET_END_HOUR

    def is_shift_active(self) -> bool:
        h = datetime.now().hour
        return SHIFT_START_HOUR <= h < SHIFT_END_HOUR

    def minutes_until_shift_end(self) -> int:
        now = datetime.now()
        shift_end = now.replace(hour=SHIFT_END_HOUR, minute=0, second=0)
        if now > shift_end:
            shift_end += timedelta(days=1)
        return int((shift_end - now).total_seconds() / 60)

    def window_label(self) -> str:
        if self.is_quiet_hours():
            return "quiet_hours"
        if self.is_shift_active():
            return "at_work"
        return "available"

    def can_send(self, priority: str = "normal") -> bool:
        if priority == "urgent":
            return True
        if self.is_quiet_hours() and priority != "high":
            return False
        return True


# ── Weight engine ─────────────────────────────────────────────────────────────

class WeightEngine:
    """
    Semantic weight accumulates per domain.
    When threshold crossed → guillotine drops → message fires.
    """

    def __init__(self):
        MSG_DIR.mkdir(parents=True, exist_ok=True)
        self._accumulated: dict[str, float] = {}

    def add_weight(self, content: str, weight: float, domain: str, source: str = "conversation"):
        self._accumulated[domain] = self._accumulated.get(domain, 0.0) + weight
        entry = {
            "content": content[:500],
            "weight": weight,
            "domain": domain,
            "source": source,
            "accumulated": self._accumulated[domain],
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        with open(WEIGHT_LOG, "a") as f:
            f.write(json.dumps(entry) + "\n")

    def check_threshold(self) -> Optional[tuple[str, float]]:
        for domain, score in self._accumulated.items():
            if score >= GUTPUNCH_THRESHOLD:
                return domain, score
        return None

    def discharge(self, domain: str):
        self._accumulated[domain] = 0.0

    def detect_deadline(self, content: str) -> bool:
        patterns = [
            r"(today|tonight|this morning|this afternoon|this evening)",
            r"(deadline|due|expires|ends|closes|last chance)",
            r"(limited time|flash sale|drops|launches|releases)",
            r"(in \d+ hours?|in \d+ minutes?)",
        ]
        c = content.lower()
        return any(re.search(p, c) for p in patterns)

    def current_weights(self) -> dict:
        return dict(self._accumulated)


# ── Telegram delivery ─────────────────────────────────────────────────────────

async def send_telegram(message: str, priority: str = "normal") -> bool:
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        return False
    try:
        import httpx
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message,
            "parse_mode": "Markdown",
        }
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.post(url, json=payload)
            return r.status_code == 200
    except Exception as e:
        print(f"[GutPunch] Telegram error: {e}")
        return False


def append_to_chain(subject: str, body: str, trigger: str, weight: float):
    MSG_DIR.mkdir(parents=True, exist_ok=True)
    prior_hash = _last_chain_hash()
    ts = datetime.now(timezone.utc).isoformat()
    entry = {
        "subject": subject,
        "body": body,
        "trigger": trigger,
        "weight": weight,
        "sent_at": ts,
        "prior_hash": prior_hash,
    }
    entry["blake3_seal"] = _seal(entry)
    with open(MSG_CHAIN, "a") as f:
        f.write(json.dumps(entry) + "\n")


# ── Public API ────────────────────────────────────────────────────────────────

_engine = WeightEngine()
_schedule = ScheduleAwareness()


def get_engine() -> WeightEngine:
    return _engine


async def add_weight_and_check(
    content: str,
    weight: float,
    domain: str,
    source: str = "agent",
) -> Optional[dict]:
    """
    Add weight and fire a message if threshold is crossed.
    Returns the sent message dict or None.
    """
    _engine.add_weight(content, weight, domain, source)
    hit = _engine.check_threshold()
    if not hit:
        return None

    domain_hit, score = hit
    if not _schedule.can_send("normal"):
        return None

    subject = f"GutPunch: {domain_hit}"
    body = (
        f"Weight threshold crossed in *{domain_hit}* "
        f"(score: {score:.2f})\n\n"
        f"Last signal: {content[:200]}"
    )

    sent = await send_telegram(f"*{subject}*\n\n{body}")
    if sent:
        _engine.discharge(domain_hit)
        append_to_chain(subject, body, "gutpunch", score)
        return {"subject": subject, "body": body, "sent": True}

    return None


async def send_proactive(subject: str, body: str, priority: str = "normal") -> bool:
    """Directly send a proactive message with schedule awareness."""
    if not _schedule.can_send(priority):
        return False
    sent = await send_telegram(f"*{subject}*\n\n{body}")
    if sent:
        append_to_chain(subject, body, "proactive", 0.0)
    return sent


def status() -> dict:
    return {
        "schedule_window": _schedule.window_label(),
        "weights": _engine.current_weights(),
        "threshold": GUTPUNCH_THRESHOLD,
        "telegram_configured": bool(TELEGRAM_TOKEN and TELEGRAM_CHAT_ID),
    }
