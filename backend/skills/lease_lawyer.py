"""
Lease Lawyer — Reads contracts and leases.
Flags weird clauses, hidden fees, and what to negotiate.
"""

import os
import json
import hashlib
import httpx
from datetime import datetime, timezone
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Optional

LAWYER_DIR = Path(".lease_lawyer")
DOCS_FILE = LAWYER_DIR / "documents.jsonl"

API_KEY = os.environ.get("GROQ_API_KEY") or os.environ.get("EMERGENT_LLM_KEY", "")
API_BASE = os.environ.get("SWARM_API_BASE", "https://api.groq.com/openai/v1")
MODEL = os.environ.get("SWARM_MODEL", "llama-3.3-70b-versatile")

RISK_LEVELS = ["low", "medium", "high", "critical"]
DOC_TYPES = ["lease", "employment", "nda", "service_agreement", "freelance", "subscription", "loan", "other"]


@dataclass
class ClauseFlag:
    clause_text: str
    issue: str
    risk_level: str
    negotiation_tip: str


@dataclass
class DocumentAnalysis:
    doc_id: str
    doc_type: str
    title: str
    party_a: str
    party_b: str
    term_months: Optional[int]
    monthly_cost: Optional[float]
    total_value: Optional[float]
    currency: str
    red_flags: list[dict]
    yellow_flags: list[dict]
    hidden_fees: list[str]
    negotiate_these: list[str]
    summary: str
    risk_score: float
    verdict: str
    analyzed_at: str


class LeaseLawyerSkill:
    def __init__(self):
        LAWYER_DIR.mkdir(parents=True, exist_ok=True)

    async def _llm(self, prompt: str, max_tokens: int = 1200) -> str:
        if not API_KEY:
            return ""
        try:
            async with httpx.AsyncClient(timeout=40) as client:
                r = await client.post(
                    f"{API_BASE}/chat/completions",
                    headers={"Authorization": f"Bearer {API_KEY}"},
                    json={"model": MODEL, "messages": [{"role": "user", "content": prompt}], "max_tokens": max_tokens},
                )
                return r.json()["choices"][0]["message"]["content"].strip()
        except Exception:
            return ""

    async def analyze(self, text: str, doc_type: str = "other", title: str = "Document") -> DocumentAnalysis:
        doc_id = hashlib.sha256(text[:500].encode()).hexdigest()[:14]
        prompt = f"""You are Lease Lawyer — a sharp legal analyst who reads contracts for regular people.
Analyze this {doc_type} document and flag EVERY problematic clause, hidden fee, and negotiation opportunity.

Document title: {title}
Type: {doc_type}

Full text:
{text[:6000]}

Respond in JSON only (no markdown):
{{
  "party_a": "<first party name>",
  "party_b": "<second party name>",
  "term_months": <contract length in months or null>,
  "monthly_cost": <recurring monthly cost as number or null>,
  "total_value": <total contract value as number or null>,
  "currency": "<USD|EUR|GBP|etc>",
  "red_flags": [
    {{"clause_text": "<exact clause>", "issue": "<why it's dangerous>", "risk_level": "high|critical", "negotiation_tip": "<what to say>"}}
  ],
  "yellow_flags": [
    {{"clause_text": "<exact clause>", "issue": "<why it's concerning>", "risk_level": "medium", "negotiation_tip": "<what to say>"}}
  ],
  "hidden_fees": ["<fee description and when it kicks in>"],
  "negotiate_these": ["<specific thing to push back on>"],
  "summary": "<2-3 sentence plain English summary>",
  "risk_score": <0.0-1.0>,
  "verdict": "<sign_as_is|negotiate|walk_away|get_real_lawyer>"
}}"""
        raw = await self._llm(prompt, max_tokens=2000)
        try:
            data = json.loads(raw)
        except Exception:
            data = {
                "party_a": "Unknown", "party_b": "Unknown", "term_months": None,
                "monthly_cost": None, "total_value": None, "currency": "USD",
                "red_flags": [], "yellow_flags": [], "hidden_fees": [],
                "negotiate_these": [], "summary": "Could not parse document.",
                "risk_score": 0.5, "verdict": "get_real_lawyer",
            }

        analysis = DocumentAnalysis(
            doc_id=doc_id, doc_type=doc_type, title=title,
            party_a=data.get("party_a", "Unknown"), party_b=data.get("party_b", "Unknown"),
            term_months=data.get("term_months"), monthly_cost=data.get("monthly_cost"),
            total_value=data.get("total_value"), currency=data.get("currency", "USD"),
            red_flags=data.get("red_flags", []), yellow_flags=data.get("yellow_flags", []),
            hidden_fees=data.get("hidden_fees", []), negotiate_these=data.get("negotiate_these", []),
            summary=data.get("summary", ""),
            risk_score=float(data.get("risk_score", 0.5)),
            verdict=data.get("verdict", "negotiate"),
            analyzed_at=datetime.now(timezone.utc).isoformat(),
        )
        with open(DOCS_FILE, "a") as f:
            f.write(json.dumps(asdict(analysis)) + "\n")
        return analysis

    async def explain_clause(self, clause_text: str) -> str:
        prompt = f"""Explain this legal clause in plain English for a non-lawyer. Be direct and specific about risks.

Clause: {clause_text}

Write 2-4 sentences. Start with what it actually means, then explain if it's good, bad, or neutral for the person signing."""
        return await self._llm(prompt, max_tokens=300) or "Could not explain clause."

    async def draft_negotiation(self, clause_text: str, desired_outcome: str) -> str:
        prompt = f"""Write a professional negotiation email asking to modify this clause.

Original clause: {clause_text}
What I want instead: {desired_outcome}

Write a short, confident, professional email paragraph (3-4 sentences). Don't be apologetic."""
        return await self._llm(prompt, max_tokens=250) or "Could not draft negotiation."

    def get_documents(self, limit: int = 20) -> list[dict]:
        if not DOCS_FILE.exists():
            return []
        lines = [l for l in DOCS_FILE.read_text().split("\n") if l.strip()]
        return [json.loads(l) for l in lines[-limit:]]

    def get_stats(self) -> dict:
        docs = self.get_documents(100)
        return {
            "total_analyzed": len(docs),
            "walk_away": len([d for d in docs if d.get("verdict") == "walk_away"]),
            "needs_negotiation": len([d for d in docs if d.get("verdict") == "negotiate"]),
            "avg_risk_score": round(sum(d.get("risk_score", 0) for d in docs) / max(len(docs), 1), 2),
            "total_red_flags": sum(len(d.get("red_flags", [])) for d in docs),
        }


_lawyer: Optional[LeaseLawyerSkill] = None

def get_lawyer() -> LeaseLawyerSkill:
    global _lawyer
    if _lawyer is None:
        _lawyer = LeaseLawyerSkill()
    return _lawyer
