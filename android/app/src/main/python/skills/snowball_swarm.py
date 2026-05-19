"""
Snowball Swarm — Lean Predefined-Role Parallel Agent System
Model-agnostic: any OpenAI-compatible endpoint. Blake3 witness chain.
Max 20 sub-agents. No dynamic role spawning. No role drift.
"""

import asyncio
import json
import hashlib
import time
import os
from datetime import datetime, timezone
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Optional

try:
    import httpx
except ImportError:
    httpx = None  # type: ignore

WITNESS_FILE = Path(".nano/swarm_witness.json")
TIMEOUT = 90


ROLES = {
    "researcher": {
        "description": "Web research, source synthesis, fact gathering",
        "system": (
            "You are a focused research specialist. Given a research sub-task, "
            "gather relevant information, synthesize key findings, and return a "
            "structured summary. Be concise. Do not pad. Return only what was asked."
        ),
    },
    "builder": {
        "description": "Code generation, file writing, technical implementation",
        "system": (
            "You are a senior software engineer. Given a build sub-task, produce "
            "clean, working code with no placeholders. Include all imports. "
            "No explanations unless asked."
        ),
    },
    "auditor": {
        "description": "Code review, logic validation, security checks",
        "system": (
            "You are a strict code auditor. Identify bugs, security issues, logic errors. "
            "Be specific. Return a structured list: critical/warning/info."
        ),
    },
    "trader": {
        "description": "Market analysis, pattern matching, signals",
        "system": (
            "You are a quantitative analyst. Given market data or a scenario, identify "
            "patterns, assess risk. Return: signal strength (strong/moderate/weak) and reasoning."
        ),
    },
    "watcher": {
        "description": "System health, heartbeat checks, anomaly detection",
        "system": (
            "You are a reliability engineer. Given system state or logs, identify anomalies. "
            "Return: status, anomalies, recommendations."
        ),
    },
    "narrator": {
        "description": "Content creation, storytelling, script writing",
        "system": (
            "You are a creative content strategist. Given a brief, produce engaging content. "
            "Match the requested tone and format exactly. No meta-commentary. Just the content."
        ),
    },
    "classifier": {
        "description": "Intent classification, routing, categorization",
        "system": (
            "You are an intent classifier. Given input text, return ONLY valid JSON: "
            "{intent, entities, confidence (0-1), suggested_route}."
        ),
    },
    "summarizer": {
        "description": "Condensing long content, extracting key points",
        "system": (
            "You are a precision summarizer. Extract only essential information. "
            "Preserve all critical facts, numbers, names. Return bullet points."
        ),
    },
    "planner": {
        "description": "Task decomposition, project planning, step sequencing",
        "system": (
            "You are a systems architect. Decompose a goal into concrete, ordered, actionable steps. "
            "Each step must be specific enough to execute without clarification. Return as JSON."
        ),
    },
    "critic": {
        "description": "Devil's advocate, assumption challenging, risk identification",
        "system": (
            "You are a critical thinker. Given any plan or idea, identify its weakest assumptions, "
            "highest risks, and most likely failure modes. Return: assumptions_challenged, risks, failure_modes."
        ),
    },
}


def _seal(data: dict) -> str:
    try:
        import blake3
        return blake3.blake3(json.dumps(data, sort_keys=True).encode()).hexdigest()
    except ImportError:
        return hashlib.sha3_256(json.dumps(data, sort_keys=True).encode()).hexdigest()


@dataclass
class SubTask:
    role: str
    task: str
    task_id: str = ""

    def __post_init__(self):
        if not self.task_id:
            self.task_id = f"{self.role}_{int(time.time()*1000)}"


@dataclass
class SubResult:
    task_id: str
    role: str
    task: str
    result: str
    success: bool
    latency_ms: int
    error: str = ""


class SnowballSwarm:
    """
    Model-agnostic parallel swarm. Uses any free provider via the Snowball backend.
    Falls back gracefully if httpx isn't available.
    """

    def __init__(
        self,
        api_key: str = "",
        api_base: str = "",
        model: str = "",
    ):
        self.api_key = api_key or os.environ.get("GROQ_API_KEY") or os.environ.get("EMERGENT_LLM_KEY", "")
        self.api_base = api_base or (
            "https://api.groq.com/openai/v1" if os.environ.get("GROQ_API_KEY")
            else "https://api.anthropic.com/v1"
        )
        self.model = model or (
            "llama-3.3-70b-versatile" if "groq" in self.api_base
            else "claude-sonnet-4-20250514"
        )

    async def run(self, task: str, allowed_roles: Optional[list[str]] = None) -> dict:
        t0 = time.time()
        run_id = f"run_{int(t0*1000)}"

        subtasks = await self._decompose(task, allowed_roles)
        if not subtasks:
            return {"error": "Failed to decompose task", "run_id": run_id}

        results = await asyncio.gather(*[
            self._run_subtask(st) for st in subtasks
        ], return_exceptions=True)

        clean_results = []
        for r in results:
            if isinstance(r, SubResult):
                clean_results.append(asdict(r))
            else:
                clean_results.append({"success": False, "error": str(r)})

        final_answer = await self._aggregate(task, clean_results)
        total_ms = int((time.time() - t0) * 1000)

        run_data = {
            "run_id": run_id,
            "task": task,
            "model": self.model,
            "subtasks": [asdict(s) for s in subtasks],
            "results": clean_results,
            "final_answer": final_answer,
            "total_latency_ms": total_ms,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        run_data["witness_hash"] = _seal(run_data)
        self._append_witness(run_data)
        return run_data

    async def _decompose(self, task: str, allowed_roles: Optional[list[str]]) -> list[SubTask]:
        roles_desc = "\n".join(
            f"  {name}: {info['description']}"
            for name, info in ROLES.items()
            if not allowed_roles or name in allowed_roles
        )
        system = (
            "You are a task orchestrator for a parallel multi-agent swarm.\n"
            "Decompose the task into parallel sub-tasks, assign each to the best role.\n\n"
            f"Available roles:\n{roles_desc}\n\n"
            "Rules:\n"
            "1. Sub-tasks must run IN PARALLEL (no dependencies between them)\n"
            "2. Max 8 sub-agents\n"
            "3. Each sub-task must be self-contained and specific\n"
            "4. Return ONLY valid JSON: {\"subtasks\": [{\"role\": \"...\", \"task\": \"...\"}]}"
        )
        raw = await self._call(system, task)
        try:
            clean = raw.strip().lstrip("```json").rstrip("```").strip()
            data = json.loads(clean)
            return [SubTask(**st) for st in data.get("subtasks", [])]
        except Exception:
            # Fallback: single researcher task
            return [SubTask(role="researcher", task=task)]

    async def _run_subtask(self, subtask: SubTask) -> SubResult:
        t0 = time.time()
        role_info = ROLES.get(subtask.role, ROLES["researcher"])
        try:
            result = await self._call(role_info["system"], subtask.task)
            return SubResult(
                task_id=subtask.task_id,
                role=subtask.role,
                task=subtask.task,
                result=result,
                success=True,
                latency_ms=int((time.time() - t0) * 1000),
            )
        except Exception as e:
            return SubResult(
                task_id=subtask.task_id,
                role=subtask.role,
                task=subtask.task,
                result="",
                success=False,
                latency_ms=int((time.time() - t0) * 1000),
                error=str(e),
            )

    async def _aggregate(self, original_task: str, results: list[dict]) -> str:
        system = (
            "You are a result aggregator for a multi-agent swarm. "
            "Synthesize all specialist outputs into a coherent, complete final answer. "
            "Resolve contradictions. Remove duplication. Return the best possible answer."
        )
        results_text = "\n\n".join(
            f"[{r.get('role','?')}] {r.get('result','(failed)')}"
            for r in results if r.get("success")
        )
        prompt = f"Original task: {original_task}\n\nSpecialist results:\n{results_text}"
        return await self._call(system, prompt)

    async def _call(self, system: str, user: str) -> str:
        if not httpx:
            return f"[httpx not available] {user[:100]}"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        is_anthropic = "anthropic.com" in self.api_base
        if is_anthropic:
            payload = {
                "model": self.model,
                "max_tokens": 2000,
                "system": system,
                "messages": [{"role": "user", "content": user}],
            }
            url = f"{self.api_base}/messages"
        else:
            payload = {
                "model": self.model,
                "max_tokens": 2000,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
            }
            url = f"{self.api_base}/chat/completions"

        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            resp = await client.post(url, headers=headers, json=payload)
            data = resp.json()
            if is_anthropic:
                return data["content"][0]["text"]
            return data["choices"][0]["message"]["content"]

    def _append_witness(self, run_data: dict):
        WITNESS_FILE.parent.mkdir(parents=True, exist_ok=True)
        chain = []
        if WITNESS_FILE.exists():
            try:
                chain = json.loads(WITNESS_FILE.read_text())
            except Exception:
                chain = []
        entry = {
            "run_id": run_data["run_id"],
            "timestamp": run_data["timestamp"],
            "task_preview": run_data["task"][:80],
            "roles": [s["role"] for s in run_data["subtasks"]],
            "success_count": sum(1 for r in run_data["results"] if r.get("success")),
            "total_ms": run_data["total_latency_ms"],
            "witness_hash": run_data["witness_hash"],
            "prior_hash": chain[-1]["witness_hash"] if chain else "genesis",
        }
        chain.append(entry)
        WITNESS_FILE.write_text(json.dumps(chain, indent=2))
