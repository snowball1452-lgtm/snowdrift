"""
Reasoning Level 1: Intentionality Prediction
Predicts user intent BEFORE responding. Classifies messages as
question / action / learning / social / complaint / creative.
Improves response relevance by understanding WHY user is asking.
"""

import re
import json
from datetime import datetime, timezone
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Optional

INTENT_DIR = Path(".reasoning_intent")
PREDICTIONS_FILE = INTENT_DIR / "predictions.jsonl"

INTENT_SIGNALS = {
    "question": {
        "patterns": [r"\?$", r"^(what|who|where|when|why|how|can you|could you|do you|is there|are there)\b"],
        "keywords": ["explain", "tell me", "clarify", "help me understand", "what is", "how do"],
        "score_weight": 1.0,
    },
    "action": {
        "patterns": [r"^(do|make|create|build|write|send|schedule|set|add|remove|delete|update|fix|run|get|fetch|find|show|list)\b"],
        "keywords": ["please", "can you do", "i need you to", "go ahead", "go and", "asap", "now"],
        "score_weight": 1.2,
    },
    "learning": {
        "patterns": [r"^(teach|help me learn|explain|show me how|how does|what's the difference|compare)\b"],
        "keywords": ["understand", "learn", "difference between", "how does", "why does", "concept"],
        "score_weight": 0.9,
    },
    "social": {
        "patterns": [r"^(hi|hey|hello|good morning|good evening|how are you|what's up|sup)\b"],
        "keywords": ["thanks", "thank you", "great", "awesome", "nice work", "love it"],
        "score_weight": 0.7,
    },
    "complaint": {
        "patterns": [r"^(this|that|it) (isn't|doesn't|won't|can't|fails|broke|wrong)"],
        "keywords": ["not working", "broken", "failed", "error", "wrong", "issue", "problem", "bug"],
        "score_weight": 1.1,
    },
    "creative": {
        "patterns": [r"^(imagine|write me|draft|design|generate|come up with|brainstorm)\b"],
        "keywords": ["idea", "concept", "story", "poem", "draft", "template", "design", "creative"],
        "score_weight": 0.85,
    },
}

URGENCY_SIGNALS = {
    "high": ["urgent", "asap", "immediately", "right now", "critical", "emergency", "deadline", "today"],
    "medium": ["soon", "when you can", "by tomorrow", "this week"],
    "low": ["whenever", "no rush", "eventually", "sometime", "later"],
}


@dataclass
class IntentPrediction:
    prediction_id: str
    message: str
    primary_intent: str
    secondary_intent: Optional[str]
    intent_scores: dict
    urgency: str
    confidence: float
    predicted_at: str


class ReasoningIntentionalitySkill:
    """
    Level 1 Advanced Reasoning: Predict WHY user is sending this message.
    Faster + more relevant responses when you know intent first.
    """

    def __init__(self):
        INTENT_DIR.mkdir(parents=True, exist_ok=True)

    def predict(self, message: str) -> dict:
        """
        Predict user intent from message text.
        Returns: primary intent, confidence, urgency, recommended response style.
        """
        import hashlib
        prediction_id = hashlib.sha256(f"{message}:{datetime.now().isoformat()}".encode()).hexdigest()[:12]

        message_lower = message.lower().strip()
        scores = {}

        for intent, config in INTENT_SIGNALS.items():
            score = 0.0

            # Pattern matching
            for pattern in config["patterns"]:
                if re.search(pattern, message_lower, re.IGNORECASE):
                    score += 0.5

            # Keyword matching
            for keyword in config["keywords"]:
                if keyword in message_lower:
                    score += 0.3

            scores[intent] = round(score * config["score_weight"], 3)

        # Normalize scores
        total = sum(scores.values()) or 1.0
        normalized = {k: round(v / total, 3) for k, v in scores.items()}

        # Top intents
        ranked = sorted(normalized.items(), key=lambda x: x[1], reverse=True)
        primary = ranked[0][0]
        secondary = ranked[1][0] if ranked[1][1] > 0.1 else None
        confidence = ranked[0][1]

        # If no clear signal, fall back to question
        if confidence < 0.1:
            primary = "question"
            confidence = 0.5

        # Urgency detection
        urgency = "medium"
        for level, signals in URGENCY_SIGNALS.items():
            if any(sig in message_lower for sig in signals):
                urgency = level
                break

        # Response style recommendation based on intent
        style_map = {
            "question": "informative — explain clearly, include examples",
            "action": "confirmatory + brief — do the thing, summarize what was done",
            "learning": "educational — step-by-step, analogies welcome",
            "social": "warm + brief — acknowledge, be friendly, don't lecture",
            "complaint": "empathetic + solution-focused — acknowledge issue first",
            "creative": "expansive — explore options, be imaginative",
        }

        result = {
            "prediction_id": prediction_id,
            "message_preview": message[:80],
            "primary_intent": primary,
            "secondary_intent": secondary,
            "intent_scores": normalized,
            "urgency": urgency,
            "confidence": round(confidence, 2),
            "recommended_style": style_map.get(primary, "balanced"),
            "predicted_at": datetime.now(timezone.utc).isoformat(),
        }

        self._log(result)
        return result

    def batch_predict(self, messages: list[str]) -> list[dict]:
        """Predict intent for multiple messages."""
        return [self.predict(m) for m in messages]

    def get_intent_distribution(self, limit: int = 100) -> dict:
        """What intents have users had? Distribution over recent messages."""
        if not PREDICTIONS_FILE.exists():
            return {}
        lines = [l for l in PREDICTIONS_FILE.read_text().split("\n") if l.strip()]
        recent = [json.loads(l) for l in lines[-limit:]]
        distribution = {}
        for r in recent:
            intent = r.get("primary_intent", "unknown")
            distribution[intent] = distribution.get(intent, 0) + 1
        return distribution

    def _log(self, prediction: dict):
        with open(PREDICTIONS_FILE, "a") as f:
            f.write(json.dumps(prediction) + "\n")

    def get_stats(self) -> dict:
        if not PREDICTIONS_FILE.exists():
            return {"total_predictions": 0}
        lines = [l for l in PREDICTIONS_FILE.read_text().split("\n") if l.strip()]
        predictions = [json.loads(l) for l in lines]
        avg_conf = sum(p.get("confidence", 0) for p in predictions) / max(len(predictions), 1)
        return {
            "total_predictions": len(predictions),
            "avg_confidence": round(avg_conf, 2),
            "intent_distribution": self.get_intent_distribution(),
        }


_intentionality: Optional[ReasoningIntentionalitySkill] = None

def get_intentionality() -> ReasoningIntentionalitySkill:
    global _intentionality
    if _intentionality is None:
        _intentionality = ReasoningIntentionalitySkill()
    return _intentionality
