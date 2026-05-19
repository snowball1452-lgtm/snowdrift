"""
Problem Reverser — Forensic diagnosis from external evidence
Reverse engineers problems from the outside-in (like a detective).
Not "why do you think?", but "what do I observe?" → trace backward.
"""

import os
import json
import hashlib
import httpx
from datetime import datetime, timezone
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Optional

REVERSER_DIR = Path(".problem_reverser")
ANALYSES_FILE = REVERSER_DIR / "analyses.jsonl"

API_KEY = os.environ.get("GROQ_API_KEY") or os.environ.get("EMERGENT_LLM_KEY", "")
API_BASE = os.environ.get("SWARM_API_BASE", "https://api.groq.com/openai/v1")
MODEL = os.environ.get("SWARM_MODEL", "llama-3.3-70b-versatile")

# Evidence categories the agent observes
EVIDENCE_TYPES = {
    "performance": ["CPU", "memory", "disk", "network", "latency"],
    "behavioral": ["patterns", "frequency", "timing", "anomalies"],
    "environmental": ["noise", "light", "temperature", "interruptions"],
    "temporal": ["time_of_day", "day_of_week", "season", "cycles"],
    "social": ["interactions", "collaboration", "communication", "isolation"],
    "systemic": ["logs", "errors", "warnings", "failed_operations"],
    "physiological": ["sleep", "energy", "focus", "stress_level"],
    "contextual": ["workload", "deadlines", "dependencies", "blockers"],
}


@dataclass
class ProblemAnalysis:
    analysis_id: str
    problem_statement: str
    observed_evidence: dict  # category → [findings]
    hypotheses: list[dict]   # ranked by likelihood
    root_cause_hypothesis: str
    confidence: float
    trace_path: list[str]    # "symptom → clue → clue → root cause"
    action_recommendations: list[str]
    analyzed_at: str


class ProblemReverserSkill:
    """Forensic problem diagnosis: observe externals, infer cause."""

    def __init__(self):
        REVERSER_DIR.mkdir(parents=True, exist_ok=True)

    async def _llm(self, prompt: str) -> str:
        if not API_KEY:
            return ""
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                r = await client.post(
                    f"{API_BASE}/chat/completions",
                    headers={"Authorization": f"Bearer {API_KEY}"},
                    json={"model": MODEL, "messages": [{"role": "user", "content": prompt}], "max_tokens": 1500},
                )
                return r.json()["choices"][0]["message"]["content"].strip()
        except Exception:
            return ""

    async def reverse_engineer(self, problem: str, observed_evidence: dict = None, context: str = "") -> dict:
        """
        Given a problem statement, reverse-engineer root cause from observable evidence.
        
        Args:
            problem: "App is slow", "Can't focus", "Sales dropped"
            observed_evidence: {"performance": ["CPU 95%", "RAM full"], "temporal": ["happens after 2pm"]}
            context: additional background
        
        Returns: analysis with hypotheses ranked by likelihood + trace path
        """
        analysis_id = hashlib.sha256(f"{problem}:{datetime.now().isoformat()}".encode()).hexdigest()[:12]

        # Build evidence prompt (what we CAN observe externally)
        evidence_sections = []
        if observed_evidence:
            for category, findings in observed_evidence.items():
                evidence_sections.append(f"{category.upper()}: {', '.join(findings)}")
        
        evidence_str = "\n".join(evidence_sections) if evidence_sections else "[NO DATA YET - agent needs to COLLECT evidence]"

        prompt = f"""You are a forensic problem detective. Reverse-engineer the ROOT CAUSE by analyzing external evidence.

PROBLEM STATEMENT: {problem}
{f'CONTEXT: {context}' if context else ''}

OBSERVED EVIDENCE (from environment, not asking user):
{evidence_str}

YOUR TASK: Work BACKWARDS from symptoms to root cause using only observable evidence.
Start with the symptom, trace through clues, find the bottleneck.

Respond in JSON:
{{
  "hypothesis_tree": [
    {{
      "hypothesis": "<root cause if X is true>",
      "likelihood": 0.85,
      "evidence_supporting": ["clue1", "clue2"],
      "evidence_against": ["missing_data"],
      "trace": ["symptom (slow app) → clue (high CPU) → clue (process_name consuming 40%) → root cause (memory leak in process)"]
    }}
  ],
  "most_likely_root_cause": "<the single most probable cause>",
  "confidence": 0.7,
  "critical_unknowns": ["What process is consuming CPU?", "Is it consistent or intermittent?"],
  "next_evidence_to_collect": ["Run top/htop", "Check error logs", "Profile with perf"],
  "action_if_correct": ["Restart service OR upgrade RAM OR optimize code"]
}}"""

        raw = await self._llm(prompt)
        try:
            data = json.loads(raw)
        except Exception:
            data = {
                "hypothesis_tree": [],
                "most_likely_root_cause": "Need more evidence to diagnose",
                "confidence": 0.2,
                "critical_unknowns": [problem],
                "next_evidence_to_collect": ["Collect detailed system metrics"],
                "action_if_correct": ["Gather more data"],
            }

        # Extract hypotheses ranked by likelihood
        hypotheses = []
        if isinstance(data.get("hypothesis_tree"), list):
            for h in data["hypothesis_tree"]:
                hypotheses.append({
                    "hypothesis": h.get("hypothesis", ""),
                    "likelihood": h.get("likelihood", 0.5),
                    "trace": h.get("trace", []),
                })
        hypotheses = sorted(hypotheses, key=lambda x: x["likelihood"], reverse=True)

        analysis = ProblemAnalysis(
            analysis_id=analysis_id,
            problem_statement=problem,
            observed_evidence=observed_evidence or {},
            hypotheses=hypotheses,
            root_cause_hypothesis=data.get("most_likely_root_cause", "Unknown"),
            confidence=float(data.get("confidence", 0.5)),
            trace_path=hypotheses[0].get("trace", []) if hypotheses else [],
            action_recommendations=data.get("action_if_correct", []),
            analyzed_at=datetime.now(timezone.utc).isoformat(),
        )

        with open(ANALYSES_FILE, "a") as f:
            f.write(json.dumps(asdict(analysis)) + "\n")

        return asdict(analysis)

    async def collect_evidence(self, problem: str, evidence_type: str = "all") -> dict:
        """
        Recommend what external data to collect for a given problem.
        Returns observable signals to gather, not questions to ask user.
        """
        if evidence_type == "all":
            relevant_types = EVIDENCE_TYPES
        else:
            relevant_types = {evidence_type: EVIDENCE_TYPES.get(evidence_type, [])}

        prompt = f"""Problem: {problem}

For this problem, what EXTERNAL, OBSERVABLE evidence should we collect?
NOT "ask the user", but "what can we measure/monitor/observe"?

Example: For "app is slow" → collect CPU%, memory%, disk I/O, network latency, error logs, not "do you feel stressed"

Evidence categories to consider:
{json.dumps(relevant_types, indent=2)}

Respond in JSON:
{{
  "priority_evidence": [
    {{"signal": "CPU usage", "how": "run top/htop", "why": "rules out compute bottleneck"}},
    {{"signal": "Error logs", "how": "tail -f /var/log/app.log", "why": "reveals failures"}}
  ],
  "collection_difficulty": "easy|medium|hard",
  "time_to_collect": "<minutes>",
  "impact": "high|medium|low"
}}"""

        raw = await self._llm(prompt)
        try:
            data = json.loads(raw)
        except Exception:
            data = {"priority_evidence": [], "collection_difficulty": "unknown", "time_to_collect": "0"}

        return data

    async def trace_backwards(self, symptom: str, hypothesis: str, collected_evidence: list[str]) -> dict:
        """
        Given a symptom, trace backwards through evidence to confirm/refute hypothesis.
        Returns the chain: symptom ← clue ← clue ← root cause
        """
        prompt = f"""Trace backwards from a symptom to diagnose root cause.

SYMPTOM (what user observes): {symptom}
HYPOTHESIS (suspected cause): {hypothesis}
EVIDENCE COLLECTED (observable facts):
{json.dumps(collected_evidence, indent=2)}

Does the evidence support or refute the hypothesis?
If supported, trace the causal chain: symptom ← what caused it ← what caused that ← root cause

Respond in JSON:
{{
  "verdict": "supported|refuted|inconclusive",
  "confidence": 0.8,
  "trace_chain": [
    "User observes: {symptom}",
    "Because: [intermediate cause from evidence]",
    "Which happened because: [another cause from evidence]",
    "ROOT CAUSE: [the fundamental issue]"
  ],
  "evidence_gaps": ["What we still need to know"],
  "next_step": "Collect more evidence OR implement fix"
}}"""

        raw = await self._llm(prompt)
        try:
            return json.loads(raw)
        except Exception:
            return {"verdict": "inconclusive", "trace_chain": [], "evidence_gaps": ["More data needed"]}

    def get_evidence_types(self) -> dict:
        """Return all observable evidence categories."""
        return EVIDENCE_TYPES

    def get_analyses(self, limit: int = 20) -> list[dict]:
        if not ANALYSES_FILE.exists():
            return []
        lines = [l for l in ANALYSES_FILE.read_text().split("\n") if l.strip()]
        return [json.loads(l) for l in lines[-limit:]]

    def get_stats(self) -> dict:
        analyses = self.get_analyses(100)
        avg_confidence = sum(a.get("confidence", 0) for a in analyses) / max(len(analyses), 1)
        return {
            "total_analyses": len(analyses),
            "avg_confidence": round(avg_confidence, 2),
            "by_problem": {a.get("problem_statement", "?")[:30]: a.get("confidence", 0) for a in analyses[:5]},
        }


_reverser: Optional[ProblemReverserSkill] = None

def get_reverser() -> ProblemReverserSkill:
    global _reverser
    if _reverser is None:
        _reverser = ProblemReverserSkill()
    return _reverser
