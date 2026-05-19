"""SnowDrift Reasoning Engine — L1 Intentionality, L4 Temporal, L11 Cognitive Load.
Single unified class replacing the three separate reasoning skill files.
Cherry-picked from main_ish — cleaner than the split-file approach.
"""

import math
import re
from datetime import datetime, timezone
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict


@dataclass
class IntentPrediction:
    """L1 — Predict WHY the user is messaging."""
    predicted_intent: str
    confidence: float
    context_clues: List[str]
    suggested_approach: str


@dataclass
class TemporalAnalysis:
    """L4 — Temporal reasoning: urgency, deadlines, priority."""
    priority_score: float
    urgency: str  # low, medium, high, critical
    time_sensitivity: bool
    deadline_detected: Optional[str]
    reasoning: str


@dataclass
class CognitiveLoadProfile:
    """L11 — Adapt response verbosity to user bandwidth."""
    estimated_load: str  # low, medium, high
    recommended_verbosity: str  # concise, normal, detailed
    max_response_tokens: int
    simplify_technical: bool
    reasoning: str


class ReasoningEngine:
    """Multi-level reasoning that runs BEFORE the agent loop."""

    INTENT_PATTERNS = {
        "help_request":      ["help", "how do i", "can you", "what is", "explain", "tell me", "show me"],
        "task_execution":    ["do", "make", "create", "set up", "install", "run", "execute", "build", "deploy"],
        "information_query": ["what", "why", "when", "where", "who", "which", "how much", "how many"],
        "troubleshooting":   ["error", "bug", "broken", "not working", "fix", "crash", "fail", "issue", "problem"],
        "browsing":          ["search", "look up", "find online", "go to", "navigate", "website", "browse", "google"],
        "device_control":    ["alarm", "timer", "call", "sms", "text", "open app", "reminder", "phone"],
        "creative":          ["write", "generate", "compose", "draft", "brainstorm", "design", "suggest"],
        "analysis":          ["analyze", "compare", "review", "evaluate", "assess", "inspect", "audit"],
        "conversation":      ["hi", "hello", "hey", "thanks", "goodbye", "bye", "sup", "yo", "what's up"],
    }

    URGENCY_SIGNALS = {
        "critical": ["asap", "urgent", "emergency", "now", "immediately", "right now", "critical"],
        "high":     ["soon", "today", "quick", "hurry", "fast", "important", "deadline"],
        "medium":   ["when you can", "later", "sometime", "eventually", "plan"],
        "low":      ["whenever", "no rush", "just curious", "idle thought", "for fun"],
    }

    COMPLEXITY_INDICATORS = {
        "high": ["detailed", "thorough", "comprehensive", "deep dive", "everything about", "full analysis"],
        "low":  ["quick", "brief", "tldr", "short", "simple", "just", "only"],
    }

    def analyze(self, message: str, history: List[Dict] = None) -> Dict:
        """Run all reasoning levels. Returns combined dict with system_modifier ready to append."""
        intent   = self.predict_intent(message, history)
        temporal = self.analyze_temporal(message)
        cognitive = self.assess_cognitive_load(message, history)

        active_levels = []
        if intent.confidence > 0.3:      active_levels.append("L1")
        if temporal.time_sensitivity:    active_levels.append("L4")
        active_levels.append("L11")      # Always on

        return {
            "active_levels":   active_levels,
            "intent":          asdict(intent),
            "temporal":        asdict(temporal),
            "cognitive":       asdict(cognitive),
            "system_modifier": self._build_system_modifier(intent, temporal, cognitive),
        }

    def predict_intent(self, message: str, history: List[Dict] = None) -> IntentPrediction:
        """L1: Predict what the user actually wants."""
        msg_lower = message.lower().strip()
        scores, clues = {}, []

        for intent, patterns in self.INTENT_PATTERNS.items():
            score = sum(1 for p in patterns if p in msg_lower)
            if score:
                scores[intent] = score / len(patterns)
                clues += [f"{intent}: '{p}'" for p in patterns if p in msg_lower]

        if not scores:
            if "?" in message:
                return IntentPrediction("information_query", 0.4, ["question mark"], "Answer directly")
            if len(message.split()) <= 3:
                return IntentPrediction("conversation", 0.3, ["short message"], "Respond conversationally")
            return IntentPrediction("task_execution", 0.2, ["general request"], "Execute the request")

        best = max(scores, key=scores.get)
        approaches = {
            "help_request":      "Explain step by step, offer to demonstrate",
            "task_execution":    "Execute immediately, show results",
            "information_query": "Answer directly, cite sources if possible",
            "troubleshooting":   "Diagnose first, then fix",
            "browsing":          "Use GhostWright to navigate and extract",
            "device_control":    "Queue device action immediately",
            "creative":          "Generate with options, ask for feedback",
            "analysis":          "Use analysis tools, present findings",
            "conversation":      "Respond naturally, keep it brief",
        }
        return IntentPrediction(
            predicted_intent=best,
            confidence=round(min(scores[best] * 2, 1.0), 2),
            context_clues=clues[:5],
            suggested_approach=approaches.get(best, "Handle appropriately"),
        )

    def analyze_temporal(self, message: str) -> TemporalAnalysis:
        """L4: Assess urgency and time sensitivity."""
        msg_lower       = message.lower()
        detected_urgency = "medium"
        time_sensitive   = False
        deadline         = None
        reasoning_parts  = []

        for urgency, signals in self.URGENCY_SIGNALS.items():
            for signal in signals:
                if signal in msg_lower:
                    detected_urgency = urgency
                    time_sensitive   = True
                    reasoning_parts.append(f"Signal: '{signal}' → {urgency}")
                    break
            if time_sensitive:
                break

        for pattern in [r"by (\d{1,2}(?::\d{2})?\s*(?:am|pm)?)", r"before (\w+ \d{1,2})",
                         r"due (\w+)", r"deadline.{0,10}(\w+ \d{1,2})"]:
            m = re.search(pattern, msg_lower)
            if m:
                deadline       = m.group(1)
                time_sensitive = True
                reasoning_parts.append(f"Deadline: {deadline}")
                break

        urgency_weights = {"critical": 1.0, "high": 0.75, "medium": 0.5, "low": 0.25}
        importance     = 0.7 if time_sensitive else 0.4
        urgency_val    = urgency_weights.get(detected_urgency, 0.5)
        deadline_hours = 2 if deadline else 24
        priority       = (importance * urgency_val) / math.log(deadline_hours + 1)

        return TemporalAnalysis(
            priority_score=round(priority, 3),
            urgency=detected_urgency,
            time_sensitivity=time_sensitive,
            deadline_detected=deadline,
            reasoning=" | ".join(reasoning_parts) or "Standard priority",
        )

    def assess_cognitive_load(self, message: str, history: List[Dict] = None) -> CognitiveLoadProfile:
        """L11: Estimate user's cognitive bandwidth and adapt verbosity."""
        msg_lower = message.lower()

        for indicator in self.COMPLEXITY_INDICATORS["low"]:
            if indicator in msg_lower:
                return CognitiveLoadProfile("high", "concise", 300, True,
                                            f"User signaled brevity: '{indicator}'")

        for indicator in self.COMPLEXITY_INDICATORS["high"]:
            if indicator in msg_lower:
                return CognitiveLoadProfile("low", "detailed", 2000, False,
                                            f"User requested depth: '{indicator}'")

        history_len = len(history) if history else 0
        if history_len > 20:
            return CognitiveLoadProfile("high", "concise", 500, True,
                                        f"Long conversation ({history_len} msgs), fatigue likely")

        return CognitiveLoadProfile("medium", "normal", 1000, False, "Standard cognitive load")

    def _build_system_modifier(self, intent: IntentPrediction,
                                temporal: TemporalAnalysis,
                                cognitive: CognitiveLoadProfile) -> str:
        parts = [
            f"\n[L1] Intent: {intent.predicted_intent} ({intent.confidence:.0%}). "
            f"Approach: {intent.suggested_approach}"
        ]
        if temporal.time_sensitivity:
            parts.append(f"[L4] Urgency: {temporal.urgency} | Priority: {temporal.priority_score} | {temporal.reasoning}")
            if temporal.urgency in ("critical", "high"):
                parts.append("Act immediately. Skip unnecessary explanations.")
        parts.append(f"[L11] Bandwidth: {cognitive.estimated_load} → {cognitive.recommended_verbosity}."
                     + (" Be concise, minimal jargon." if cognitive.simplify_technical else ""))
        return "\n".join(parts)


# Module-level singleton
_engine: Optional[ReasoningEngine] = None

def get_reasoning() -> ReasoningEngine:
    global _engine
    if _engine is None:
        _engine = ReasoningEngine()
    return _engine
