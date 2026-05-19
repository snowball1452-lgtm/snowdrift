"""
SnowballBot Key Rotator — Circuit Breaker + Quota Tracker
Wraps call_free_provider_llm with intelligent failure handling.
- Circuit breaks on error, auto-recovers after 60s
- Tracks usage, rotates at 90% of daily quota
- Works with 1..N keys per provider
"""

import time
import logging
from dataclasses import dataclass, field
from typing import Optional, Dict

log = logging.getLogger("KeyRotator")


@dataclass
class ProviderKey:
    name: str
    provider: str
    api_key: str
    daily_limit: int = 0        # 0 = unlimited / unknown
    monthly_limit: int = 0
    used_today: int = 0
    used_month: int = 0
    last_reset: float = field(default_factory=time.time)
    last_used: float = 0.0
    tripped: bool = False
    tripped_at: float = 0.0
    trip_reason: str = ""
    success_count: int = 0
    error_count: int = 0

    def quota_pct(self) -> float:
        if self.daily_limit > 0:
            return self.used_today / self.daily_limit
        if self.monthly_limit > 0:
            return self.used_month / self.monthly_limit
        return 0.0

    def is_healthy(self) -> bool:
        if self.tripped:
            if time.time() - self.tripped_at > 60:
                self.tripped = False
                self.trip_reason = ""
                log.info(f"[KeyRotator] {self.name} recovered after 60s")
            else:
                return False
        if self.quota_pct() >= 0.90:
            log.info(f"[KeyRotator] {self.name} near quota ({self.quota_pct():.0%}), rotating")
            return False
        return True

    def trip(self, reason: str):
        self.tripped = True
        self.tripped_at = time.time()
        self.trip_reason = reason
        self.error_count += 1
        log.warning(f"[KeyRotator] TRIPPED {self.name}: {reason}")

    def record_use(self, tokens: int = 1):
        self.used_today += tokens
        self.used_month += tokens
        self.last_used = time.time()
        self.success_count += 1

    def reset_daily(self):
        self.used_today = 0
        self.last_reset = time.time()

    def status(self) -> dict:
        return {
            "name": self.name,
            "provider": self.provider,
            "healthy": self.is_healthy(),
            "quota_pct": round(self.quota_pct() * 100, 1),
            "used_today": self.used_today,
            "success_count": self.success_count,
            "error_count": self.error_count,
            "tripped": self.tripped,
            "trip_reason": self.trip_reason or None,
        }


class ProviderRotator:
    """
    Round-robin across healthy keys per provider.
    Maintains a pointer per provider for even wear.
    """

    def __init__(self):
        self._keys: Dict[str, list[ProviderKey]] = {}
        self._pointers: Dict[str, int] = {}

    def add_key(self, key: ProviderKey):
        if key.provider not in self._keys:
            self._keys[key.provider] = []
        # Avoid duplicates
        existing = [k for k in self._keys[key.provider] if k.api_key == key.api_key]
        if not existing:
            self._keys[key.provider].append(key)

    def get_key(self, provider: str) -> Optional[ProviderKey]:
        candidates = [k for k in self._keys.get(provider, []) if k.is_healthy()]
        if not candidates:
            # All tripped — try any recovering
            recovering = [
                k for k in self._keys.get(provider, [])
                if k.tripped and time.time() - k.tripped_at > 60
            ]
            if recovering:
                recovering[0].tripped = False
                return recovering[0]
            return None
        idx = self._pointers.get(provider, 0) % len(candidates)
        self._pointers[provider] = idx + 1
        return candidates[idx]

    def report_success(self, provider: str, api_key: str, tokens: int = 1):
        for k in self._keys.get(provider, []):
            if k.api_key == api_key:
                k.record_use(tokens)
                return

    def report_error(self, provider: str, api_key: str, reason: str):
        for k in self._keys.get(provider, []):
            if k.api_key == api_key:
                k.trip(reason)
                return

    def update_from_headers(self, provider: str, api_key: str, headers: dict):
        """Parse rate-limit headers from provider responses."""
        for k in self._keys.get(provider, []):
            if k.api_key != api_key:
                continue
            # OpenAI / OpenRouter / Groq style
            remaining = headers.get("x-ratelimit-remaining-requests")
            limit = headers.get("x-ratelimit-limit-requests")
            if remaining and limit:
                k.daily_limit = int(limit)
                k.used_today = int(limit) - int(remaining)
                return
            # Anthropic style
            remaining = headers.get("anthropic-ratelimit-requests-remaining")
            limit = headers.get("anthropic-ratelimit-requests-limit")
            if remaining and limit:
                k.daily_limit = int(limit)
                k.used_today = int(limit) - int(remaining)

    def status(self) -> list[dict]:
        out = []
        for provider, keys in self._keys.items():
            for k in keys:
                out.append(k.status())
        return out

    def is_provider_healthy(self, provider: str) -> bool:
        return self.get_key(provider) is not None


# ── Global singleton ──────────────────────────────────────────────────────────

_rotator = ProviderRotator()


def get_rotator() -> ProviderRotator:
    return _rotator


def ensure_key(provider: str, api_key: str, daily_limit: int = 0):
    """Register a key into the global rotator (idempotent)."""
    if not api_key:
        return
    _rotator.add_key(ProviderKey(
        name=f"{provider}-key",
        provider=provider,
        api_key=api_key,
        daily_limit=daily_limit,
    ))


# ── Free provider quota table ─────────────────────────────────────────────────

FREE_DAILY_LIMITS = {
    "groq":        14_400,
    "together":    0,          # $25 credit, not daily-limited
    "openrouter":  50,         # free tier ~50/day
    "cerebras":    0,          # 1M tokens/day — token not request limited
    "mistral":     0,          # free tier, not request limited
    "cohere":      1_000,      # free trial ~1000/mo
    "gemini_direct": 1_500,    # 1500 req/day free
}
