"""
Council — 3-Stage Multi-Model Debate Skill

Ask N models the same question independently (Stage 1),
show them each other's answers anonymously (Stage 2),
synthesize into one verdict (Stage 3).

Inspired by karpathy/llm-council's anonymized peer-review pattern,
adapted for SnowDrift's on-device LlmChat + swarm architecture.

Premium skill — $3 standalone or part of the $12 Skills Pack.
"""

import asyncio
import json
import hashlib
import time
import os
from datetime import datetime, timezone
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Optional, Dict, List

try:
    import httpx
except ImportError:
    httpx = None  # type: ignore

COUNCIL_DIR = Path(".council")
COUNCIL_LOG = COUNCIL_DIR / "debates.jsonl"
TIMEOUT = 90

# ── Council Configuration ──────────────────────────────────────────────
# Three perspectives: deep analysis, practical execution, minimal essence.
DEFAULT_COUNCIL = {
    "alpha": {
        "name": "Deep Analyst",
        "system": (
            "You are a Deep Analyst. Think carefully about this question. "
            "Consider edge cases, second-order effects, and hidden assumptions. "
            "Be thorough. Explore multiple angles. Show your reasoning. "
            "Do not be brief — depth is your strength."
        ),
        "model_env": "COUNCIL_ALPHA_MODEL",
        "default_model": "claude-sonnet-4-20250514",
        "default_provider": "anthropic",
    },
    "beta": {
        "name": "Practical Builder",
        "system": (
            "You are a Practical Builder. Cut through theory and give actionable steps. "
            "If someone asked this question, they want to DO something, not read a thesis. "
            "Give concrete steps, real examples, and specific tools. "
            "Be direct. Prioritize what works over what's elegant."
        ),
        "model_env": "COUNCIL_BETA_MODEL",
        "default_model": "llama-3.3-70b-versatile",
        "default_provider": "groq",
    },
    "gamma": {
        "name": "Minimalist Sage",
        "system": (
            "You are a Minimalist Sage. Find the essential core of this question. "
            "What is the ONE thing that matters most? Strip away noise and decoration. "
            "Give the shortest answer that is still correct and useful. "
            "If you can say it in one sentence, do it. Maximum signal, minimum words."
        ),
        "model_env": "COUNCIL_GAMMA_MODEL",
        "default_model": "gemini-2.0-flash",
        "default_provider": "google",
    },
}

# The Chairman synthesizes all perspectives into a final verdict
CHAIRMAN_SYSTEM = (
    "You are the Chairman of a Council. Three experts have debated a question:\n"
    "  Alpha (Deep Analyst) — thorough, explores edge cases\n"
    "  Beta (Practical Builder) — direct, actionable, concrete steps\n"
    "  Gamma (Minimalist Sage) — essential core, shortest correct answer\n\n"
    "Your job: Synthesize their perspectives into ONE final verdict.\n"
    "Respect each perspective's strength. The verdict should:\n"
    "  1. State the core answer clearly (borrow from Gamma)\n"
    "  2. Add depth where it matters (borrow from Alpha)\n"
    "  3. Include concrete next steps (borrow from Beta)\n"
    "  4. Note any disagreements between the experts\n"
    "  5. Give a confidence score (0-100) and divergence score (0-100)\n\n"
    "Return your verdict in this EXACT format:\n"
    "VERDICT: <one sentence answer>\n"
    "DEPTH: <2-3 sentences expanding if needed>\n"
    "STEPS: <numbered concrete actions>\n"
    "DISAGREEMENTS: <any conflicts between experts, or 'None'>\n"
    "CONFIDENCE: <0-100>\n"
    "DIVERGENCE: <0-100, how much did experts disagree>"
)

RANKING_SYSTEM = (
    "You are an expert evaluator. You will see {count} anonymous responses to a question, "
    "labeled only as Response A, B, C, etc. You do NOT know which model wrote which response.\n\n"
    "Rank them from best to worst. Consider:\n"
    "  - Accuracy and completeness\n"
    "  - Usefulness and actionability\n"
    "  - Clarity and conciseness\n\n"
    "Return ONLY valid JSON:\n"
    '{{"rankings": [{{"label": "A", "rank": 1, "reason": "..."}}], "best_aspect": "...", "worst_aspect": "..."}}'
)


@dataclass
class CouncilResult:
    """Complete result of a council debate."""
    question: str
    stage1_responses: Dict[str, dict]    # {alpha: {...}, beta: {...}, gamma: {...}}
    stage2_rankings: Dict[str, dict]       # {alpha: {...}, beta: {...}, gamma: {...}}
    stage3_verdict: dict                    # Chairman's synthesis
    total_latency_ms: int
    timestamp: str = ""
    run_id: str = ""
    witness_hash: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()
        if not self.run_id:
            self.run_id = f"council_{int(time.time()*1000)}"


class CouncilSkill:
    """
    3-Stage Multi-Model Council Debate.

    Stage 1: Ask Alpha, Beta, Gamma the same question independently
    Stage 2: Show each model the other responses ANONYMIZED, ask for rankings
    Stage 3: Chairman synthesizes all responses + rankings into one verdict

    The anonymization prevents models from playing favorites — they rank
    purely on quality, not on brand loyalty.
    """

    def __init__(
        self,
        api_key: str = "",
        api_base: str = "",
    ):
        self.api_key = api_key or os.environ.get(
            "EMERGENT_LLM_KEY",
            os.environ.get("GROQ_API_KEY", "")
        )
        # Build api_base per provider from env
        self.api_bases = {
            "anthropic": "https://api.anthropic.com/v1",
            "groq": "https://api.groq.com/openai/v1",
            "google": "https://generativelanguage.googleapis.com/v1beta/openai",
            "openai": "https://api.openai.com/v1",
            "ollama": "http://127.0.0.1:11434/v1",
        }

    async def deliberate(self, question: str, council_config: Optional[dict] = None) -> CouncilResult:
        """
        Run a full 3-stage council debate on the given question.

        Args:
            question: The question to debate
            council_config: Override default council members (optional)

        Returns:
            CouncilResult with all stage outputs and final verdict
        """
        t0 = time.time()
        council = council_config or DEFAULT_COUNCIL
        labels = list(council.keys())

        # ── Stage 1: Independent Responses ──────────────────────────
        stage1_tasks = {
            label: self._call_council_member(label, question, council[label])
            for label in labels
        }
        stage1_responses = {}
        results = await asyncio.gather(*stage1_tasks.values(), return_exceptions=True)
        for label, result in zip(labels, results):
            if isinstance(result, Exception):
                stage1_responses[label] = {
                    "response": f"[Error: {result}]",
                    "success": False,
                    "latency_ms": 0,
                }
            else:
                stage1_responses[label] = result

        # ── Stage 2: Anonymized Peer Review ─────────────────────────
        stage2_rankings = {}
        if any(r.get("success") for r in stage1_responses.values()):
            stage2_tasks = {
                label: self._rank_responses(label, question, stage1_responses, council[label])
                for label in labels
            }
            rankings_results = await asyncio.gather(*stage2_tasks.values(), return_exceptions=True)
            for label, result in zip(labels, rankings_results):
                if isinstance(result, Exception):
                    stage2_rankings[label] = {"rankings": [], "error": str(result)}
                else:
                    stage2_rankings[label] = result

        # ── Stage 3: Chairman Synthesis ─────────────────────────────
        stage3_verdict = await self._chairman_synthesize(
            question, stage1_responses, stage2_rankings
        )

        total_ms = int((time.time() - t0) * 1000)

        result = CouncilResult(
            question=question,
            stage1_responses=stage1_responses,
            stage2_rankings=stage2_rankings,
            stage3_verdict=stage3_verdict,
            total_latency_ms=total_ms,
        )

        # Witness hash for integrity
        result.witness_hash = self._seal(asdict(result))
        self._log_debate(result)

        return result

    async def _call_council_member(
        self, label: str, question: str, config: dict
    ) -> dict:
        """Call a single council member for Stage 1."""
        t0 = time.time()
        system_prompt = config.get("system", "You are a helpful assistant.")
        response = await self._call_llm(
            provider=config.get("default_provider", "groq"),
            model=config.get("default_model", "llama-3.3-70b-versatile"),
            system=system_prompt,
            user=question,
        )
        latency = int((time.time() - t0) * 1000)
        return {
            "response": response,
            "success": not response.startswith("[Error:"),
            "latency_ms": latency,
            "model": config.get("default_model", "?"),
            "name": config.get("name", label),
        }

    async def _rank_responses(
        self, label: str, question: str, all_responses: dict, config: dict
    ) -> dict:
        """
        Stage 2: Show each member the OTHER responses (anonymized)
        and ask for rankings. Models never see their own response labeled.
        """
        # Build anonymized list (exclude this member's own response)
        other_labels = [l for l in all_responses if l != label]
        anonymized = {}
        letter_map = {}
        for i, other_label in enumerate(other_labels):
            letter = chr(65 + i)  # A, B, C...
            letter_map[letter] = other_label
            resp = all_responses.get(other_label, {})
            anonymized[letter] = resp.get("response", "(failed)")

        # Format the ranking prompt
        responses_text = "\n\n".join(
            f"Response {letter}:\n{resp}"
            for letter, resp in anonymized.items()
        )
        ranking_prompt = (
            f"Question: {question}\n\n"
            f"{responses_text}\n\n"
            f"Rank these {len(anonymized)} responses from best to worst. "
            "Return ONLY valid JSON."
        )

        response = await self._call_llm(
            provider=config.get("default_provider", "groq"),
            model=config.get("default_model", "llama-3.3-70b-versatile"),
            system=RANKING_SYSTEM.format(count=len(anonymized)),
            user=ranking_prompt,
        )

        # Parse rankings
        try:
            clean = response.strip().lstrip("```json").rstrip("```").strip()
            rankings_data = json.loads(clean)
        except (json.JSONDecodeError, AttributeError):
            rankings_data = {
                "rankings": [],
                "parse_error": "Could not parse ranking response",
            }

        # Map back from anonymous labels
        if "rankings" in rankings_data:
            for ranking in rankings_data.get("rankings", []):
                letter = ranking.get("label", "")
                if letter in letter_map:
                    ranking["actual_member"] = letter_map[letter]

        return rankings_data

    async def _chairman_synthesize(
        self, question: str, stage1: dict, stage2: dict
    ) -> dict:
        """Stage 3: Chairman reads all responses + rankings, synthesizes verdict."""
        # Build the synthesis prompt
        debate_text = ""
        for label, resp in stage1.items():
            name = resp.get("name", label)
            response = resp.get("response", "(no response)")
            debate_text += f"\n{name} (Stage 1):\n{response}\n"

        debate_text += "\n--- Stage 2: Peer Rankings ---\n"
        for label, ranking in stage2.items():
            name = stage1.get(label, {}).get("name", label)
            debate_text += f"\n{name}'s rankings:\n"
            for r in ranking.get("rankings", []):
                actual = r.get("actual_member", r.get("label", "?"))
                rank = r.get("rank", "?")
                reason = r.get("reason", "")
                debate_text += f"  Rank {rank}: {actual} — {reason}\n"

        verdict = await self._call_llm(
            provider="anthropic",  # Chairman uses the best model available
            model="claude-sonnet-4-20250514",
            system=CHAIRMAN_SYSTEM,
            user=f"Question: {question}\n\n--- Stage 1: Expert Responses ---{debate_text}",
        )

        # Parse the structured verdict
        return self._parse_verdict(verdict)

    def _parse_verdict(self, raw: str) -> dict:
        """Parse the Chairman's structured verdict."""
        verdict = {
            "raw": raw,
            "synthesis": "",
            "confidence": 0,
            "divergence": 0,
            "steps": [],
            "disagreements": "",
        }

        for line in raw.split("\n"):
            line = line.strip()
            if line.upper().startswith("VERDICT:"):
                verdict["synthesis"] = line[8:].strip()
            elif line.upper().startswith("CONFIDENCE:"):
                try:
                    verdict["confidence"] = int("".join(c for c in line[12:] if c.isdigit()))
                except ValueError:
                    pass
            elif line.upper().startswith("DIVERGENCE:"):
                try:
                    verdict["divergence"] = int("".join(c for c in line[11:] if c.isdigit()))
                except ValueError:
                    pass
            elif line.upper().startswith("STEPS:"):
                verdict["steps_started"] = True
            elif line.upper().startswith("DISAGREEMENTS:"):
                verdict["disagreements"] = line[14:].strip()

        # Extract steps (numbered lines after STEPS:)
        steps = []
        in_steps = False
        for line in raw.split("\n"):
            stripped = line.strip()
            if stripped.upper().startswith("STEPS:"):
                in_steps = True
                continue
            if in_steps:
                if stripped and stripped[0].isdigit():
                    steps.append(stripped)
                elif stripped.upper().startswith(("DEPTH:", "DISAGREEMENTS:", "CONFIDENCE:")):
                    in_steps = False
        verdict["steps"] = steps

        return verdict

    async def _call_llm(
        self, provider: str, model: str, system: str, user: str
    ) -> str:
        """Call an LLM via the appropriate provider."""
        if not httpx:
            return f"[httpx not available] {user[:100]}"

        api_key = self.api_key
        # Provider-specific key overrides
        key_env_map = {
            "anthropic": "ANTHROPIC_API_KEY",
            "groq": "GROQ_API_KEY",
            "google": "GOOGLE_API_KEY",
            "openai": "OPENAI_API_KEY",
        }
        if provider in key_env_map:
            api_key = os.environ.get(key_env_map[provider], api_key)

        api_base = self.api_bases.get(provider, "https://api.groq.com/openai/v1")

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        is_anthropic = provider == "anthropic"

        if is_anthropic:
            payload = {
                "model": model,
                "max_tokens": 2000,
                "system": system,
                "messages": [{"role": "user", "content": user}],
            }
            url = f"{api_base}/messages"
            headers["x-api-key"] = api_key
            if "Authorization" in headers:
                del headers["Authorization"]
        else:
            payload = {
                "model": model,
                "max_tokens": 2000,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
            }
            url = f"{api_base}/chat/completions"

        try:
            async with httpx.AsyncClient(timeout=TIMEOUT) as client:
                resp = await client.post(url, headers=headers, json=payload)
                data = resp.json()
                if is_anthropic:
                    return data["content"][0]["text"]
                return data["choices"][0]["message"]["content"]
        except Exception as e:
            return f"[Error: {e}]"

    @staticmethod
    def _seal(data: dict) -> str:
        """Blake3/seal for witness integrity (same pattern as Swarm)."""
        try:
            import blake3
            return blake3.blake3(json.dumps(data, sort_keys=True).encode()).hexdigest()
        except ImportError:
            return hashlib.sha3_256(json.dumps(data, sort_keys=True).encode()).hexdigest()

    def _log_debate(self, result: CouncilResult):
        """Append debate to JSONL log for audit trail."""
        COUNCIL_DIR.mkdir(parents=True, exist_ok=True)
        entry = {
            "run_id": result.run_id,
            "question_preview": result.question[:80],
            "confidence": result.stage3_verdict.get("confidence", 0),
            "divergence": result.stage3_verdict.get("divergence", 0),
            "total_ms": result.total_latency_ms,
            "witness_hash": result.witness_hash,
            "timestamp": result.timestamp,
        }
        with open(COUNCIL_LOG, "a") as f:
            f.write(json.dumps(entry) + "\n")

    def format_result(self, result: CouncilResult) -> str:
        """Format a CouncilResult into a human-readable string."""
        lines = [
            f"🏛️ **Council Verdict**",
            f"",
            f"**Question:** {result.question}",
            f"",
        ]

        # Stage 1 summaries
        lines.append("**Stage 1 — Expert Responses:**")
        for label, resp in result.stage1_responses.items():
            name = resp.get("name", label)
            model = resp.get("model", "?")
            latency = resp.get("latency_ms", "?")
            response_preview = resp.get("response", "")[:200]
            if len(resp.get("response", "")) > 200:
                response_preview += "..."
            lines.append(f"  • **{name}** ({model}, {latency}ms): {response_preview}")
        lines.append("")

        # Verdict
        verdict = result.stage3_verdict
        lines.append(f"**Verdict:** {verdict.get('synthesis', 'N/A')}")
        if verdict.get("steps"):
            lines.append(f"")
            lines.append(f"**Next Steps:**")
            for step in verdict.get("steps", []):
                lines.append(f"  {step}")
        if verdict.get("disagreements") and verdict.get("disagreements") != "None":
            lines.append(f"")
            lines.append(f"**Disagreements:** {verdict['disagreements']}")
        lines.append(f"")
        lines.append(
            f"Confidence: **{verdict.get('confidence', 0)}%** | "
            f"Divergence: **{verdict.get('divergence', 0)}%** | "
            f"Latency: **{result.total_latency_ms}ms**"
        )

        return "\n".join(lines)


# ── Module-level singleton ─────────────────────────────────────────────
_council: Optional[CouncilSkill] = None


def get_council() -> CouncilSkill:
    global _council
    if _council is None:
        _council = CouncilSkill()
    return _council