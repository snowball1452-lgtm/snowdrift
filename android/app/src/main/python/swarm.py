"""
SnowballBot Swarm - Multi-agent orchestration inspired by Kimi K2.5.
Decomposes complex tasks into subtasks and spawns specialized worker agents.
"""

import asyncio
import uuid
import json
import time
from datetime import datetime
from typing import List, Dict, Optional, Any
from emergentintegrations.llm.chat import LlmChat, UserMessage
import os
from dotenv import load_dotenv

load_dotenv()

EMERGENT_KEY = os.environ.get("EMERGENT_LLM_KEY", "")

# Worker agent specializations
WORKER_PROFILES = {
    "browser": {
        "name": "Browser Agent",
        "icon": "🌐",
        "system_prompt": """You are a Browser Worker Agent. Your job is to browse websites, extract data, and interact with web pages.
You have access to browse actions: navigate, act, extract, observe, screenshot.
Return your findings as structured JSON with keys: summary, data, links, next_steps.
Be concise and focused on the assigned subtask.""",
    },
    "code": {
        "name": "Code Agent",
        "icon": "💻",
        "system_prompt": """You are a Code Worker Agent. Your job is to write, analyze, and execute code.
You can execute shell commands and Python scripts.
Return your results as structured JSON with keys: summary, code, output, errors.
Be precise and include working code.""",
    },
    "research": {
        "name": "Research Agent",
        "icon": "🔍",
        "system_prompt": """You are a Research Worker Agent. Your job is to gather information, analyze data, and provide insights.
You can browse the web and extract content from pages.
Return your findings as structured JSON with keys: summary, findings, sources, confidence.
Be thorough but concise.""",
    },
    "device": {
        "name": "Device Agent",
        "icon": "📱",
        "system_prompt": """You are a Device Worker Agent. Your job is to control phone actions.
You can set alarms, send SMS, make calls, open apps, create reminders.
Return your results as structured JSON with keys: summary, actions_taken, status.
Confirm each action taken.""",
    },
    "analyst": {
        "name": "Analyst Agent",
        "icon": "📊",
        "system_prompt": """You are an Analyst Worker Agent. Your job is to analyze data, find patterns, and provide insights.
You receive data from other agents and synthesize it.
Return your analysis as structured JSON with keys: summary, insights, recommendations, confidence.
Be analytical and data-driven.""",
    },
}

ORCHESTRATOR_PROMPT = """You are the SnowballBot Swarm Orchestrator. Your job is to decompose complex tasks into subtasks and assign them to specialized worker agents.

Available workers:
- browser: Web browsing, scraping, form filling, page interaction
- code: Code writing, execution, analysis, debugging
- research: Information gathering, web search, content extraction
- device: Phone actions (alarms, SMS, calls, apps)
- analyst: Data analysis, pattern recognition, insights

RULES:
1. Analyze the user's request and break it into independent subtasks
2. Assign each subtask to the most appropriate worker
3. Identify which tasks can run in PARALLEL vs which need SEQUENTIAL execution
4. Keep subtasks focused and atomic
5. Maximum 5 subtasks per decomposition

Respond ONLY with valid JSON in this exact format:
{
    "plan": "Brief description of your decomposition strategy",
    "subtasks": [
        {
            "id": "t1",
            "worker": "browser|code|research|device|analyst",
            "task": "Specific instruction for this worker",
            "depends_on": [],
            "priority": 1
        }
    ],
    "aggregation": "How to combine results into a final answer"
}"""


class SwarmTask:
    """A single subtask in the swarm."""
    def __init__(self, task_id: str, worker_type: str, instruction: str, depends_on: List[str] = None, priority: int = 1):
        self.id = task_id
        self.worker_type = worker_type
        self.instruction = instruction
        self.depends_on = depends_on or []
        self.priority = priority
        self.status = "pending"  # pending, running, completed, failed
        self.result: Optional[Dict] = None
        self.started_at: Optional[str] = None
        self.completed_at: Optional[str] = None
        self.error: Optional[str] = None

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "worker": self.worker_type,
            "worker_name": WORKER_PROFILES.get(self.worker_type, {}).get("name", self.worker_type),
            "worker_icon": WORKER_PROFILES.get(self.worker_type, {}).get("icon", "🤖"),
            "instruction": self.instruction,
            "depends_on": self.depends_on,
            "priority": self.priority,
            "status": self.status,
            "result": self.result,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "error": self.error,
        }


class SwarmJob:
    """A complete swarm job with multiple subtasks."""
    def __init__(self, job_id: str, original_query: str):
        self.id = job_id
        self.original_query = original_query
        self.plan: str = ""
        self.aggregation_strategy: str = ""
        self.tasks: Dict[str, SwarmTask] = {}
        self.status = "planning"  # planning, executing, aggregating, completed, failed
        self.final_result: Optional[str] = None
        self.consensus: Optional[Dict] = None
        self.created_at = datetime.utcnow().isoformat()
        self.completed_at: Optional[str] = None

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "query": self.original_query,
            "plan": self.plan,
            "status": self.status,
            "tasks": [t.to_dict() for t in self.tasks.values()],
            "final_result": self.final_result,
            "consensus": self.consensus,
            "created_at": self.created_at,
            "completed_at": self.completed_at,
            "progress": self._progress(),
        }

    def _progress(self) -> Dict:
        total = len(self.tasks)
        if total == 0:
            return {"total": 0, "completed": 0, "running": 0, "pending": 0, "failed": 0, "percent": 0}
        completed = sum(1 for t in self.tasks.values() if t.status == "completed")
        running = sum(1 for t in self.tasks.values() if t.status == "running")
        failed = sum(1 for t in self.tasks.values() if t.status == "failed")
        pending = total - completed - running - failed
        return {
            "total": total, "completed": completed, "running": running,
            "pending": pending, "failed": failed,
            "percent": int((completed / total) * 100),
        }


class SwarmOrchestrator:
    """Orchestrates multi-agent swarm execution."""

    def __init__(self):
        self.jobs: Dict[str, SwarmJob] = {}
        self._action_handlers: Dict[str, Any] = {}

    def register_action_handler(self, action_type: str, handler):
        """Register external action handlers (browse, execute, device_action)."""
        self._action_handlers[action_type] = handler

    async def decompose(self, query: str) -> SwarmJob:
        """Use LLM to decompose a complex task into subtasks."""
        job_id = str(uuid.uuid4())[:8]
        job = SwarmJob(job_id, query)
        self.jobs[job_id] = job

        try:
            chat = LlmChat(
                api_key=EMERGENT_KEY,
                session_id=f"swarm-orch-{job_id}",
                system_message=ORCHESTRATOR_PROMPT,
            )
            chat.with_model("gemini", "gemini-2.5-flash")
            response = await chat.send_message(UserMessage(text=f"Decompose this task: {query}"))
            text = response.strip() if isinstance(response, str) else response.text.strip()

            # Parse JSON from response
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0].strip()
            elif "```" in text:
                text = text.split("```")[1].split("```")[0].strip()

            plan_data = json.loads(text)
            job.plan = plan_data.get("plan", "")
            job.aggregation_strategy = plan_data.get("aggregation", "")

            for st in plan_data.get("subtasks", []):
                task = SwarmTask(
                    task_id=st.get("id", str(uuid.uuid4())[:4]),
                    worker_type=st.get("worker", "research"),
                    instruction=st.get("task", ""),
                    depends_on=st.get("depends_on", []),
                    priority=st.get("priority", 1),
                )
                job.tasks[task.id] = task

            job.status = "executing"
        except Exception as e:
            job.status = "failed"
            job.final_result = f"Failed to decompose task: {str(e)}"

        return job

    async def execute_job(self, job: SwarmJob, process_action_fn=None) -> SwarmJob:
        """Execute all subtasks, respecting dependencies and parallelism."""
        if job.status != "executing":
            return job

        max_iterations = 10
        iteration = 0

        while iteration < max_iterations:
            iteration += 1

            # Find tasks ready to run (dependencies met)
            ready = []
            for task in job.tasks.values():
                if task.status != "pending":
                    continue
                deps_met = all(
                    job.tasks.get(dep, SwarmTask("", "", "")).status == "completed"
                    for dep in task.depends_on
                )
                if deps_met:
                    ready.append(task)

            if not ready:
                # Check if all done or stuck
                pending = [t for t in job.tasks.values() if t.status == "pending"]
                if not pending:
                    break
                # Stuck - force remaining
                for t in pending:
                    t.status = "failed"
                    t.error = "Dependencies not met"
                break

            # Execute ready tasks in parallel
            async def run_task(task: SwarmTask):
                task.status = "running"
                task.started_at = datetime.utcnow().isoformat()
                try:
                    result = await self._execute_worker(task, job, process_action_fn)
                    task.result = result
                    task.status = "completed"
                except Exception as e:
                    task.error = str(e)
                    task.status = "failed"
                task.completed_at = datetime.utcnow().isoformat()

            await asyncio.gather(*[run_task(t) for t in ready])

        # Aggregate results
        job.status = "aggregating"
        try:
            job.final_result = await self._aggregate_results(job)
            job.status = "completed"
        except Exception as e:
            job.final_result = f"Aggregation failed: {str(e)}"
            job.status = "completed"

        job.completed_at = datetime.utcnow().isoformat()
        return job

    async def _execute_worker(self, task: SwarmTask, job: SwarmJob, process_action_fn=None) -> Dict:
        """Execute a single worker task."""
        profile = WORKER_PROFILES.get(task.worker_type, WORKER_PROFILES["research"])

        # Build context from dependency results
        dep_context = ""
        for dep_id in task.depends_on:
            dep_task = job.tasks.get(dep_id)
            if dep_task and dep_task.result:
                dep_context += f"\n--- Result from {dep_task.worker_type} (task {dep_id}) ---\n"
                dep_context += json.dumps(dep_task.result, indent=2)[:1000]
                dep_context += "\n"

        prompt = f"""Task: {task.instruction}

{f'Context from previous tasks:{dep_context}' if dep_context else ''}

Respond with a JSON object containing your results. Be concise."""

        try:
            chat = LlmChat(
                api_key=EMERGENT_KEY,
                session_id=f"swarm-worker-{task.id}",
                system_message=profile["system_prompt"],
            )
            chat.with_model("gemini", "gemini-2.5-flash")
            response = await chat.send_message(UserMessage(text=prompt))
            text = response.strip() if isinstance(response, str) else response.text.strip()

            # Try to parse as JSON
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0].strip()
            elif "```" in text:
                text = text.split("```")[1].split("```")[0].strip()

            try:
                return json.loads(text)
            except:
                return {"summary": text[:1000], "raw": True}
        except Exception as e:
            return {"error": str(e)}

    async def _aggregate_results(self, job: SwarmJob) -> str:
        """Aggregate all worker results into a final response."""
        results_text = ""
        for task in job.tasks.values():
            icon = WORKER_PROFILES.get(task.worker_type, {}).get("icon", "🤖")
            results_text += f"\n{icon} **{task.worker_type.title()} Agent** ({task.id}):\n"
            if task.status == "completed" and task.result:
                summary = task.result.get("summary", json.dumps(task.result)[:500])
                results_text += f"{summary}\n"
            elif task.status == "failed":
                results_text += f"Failed: {task.error}\n"

        # Use LLM to create final synthesis
        try:
            chat = LlmChat(
                api_key=EMERGENT_KEY,
                session_id=f"swarm-agg-{job.id}",
                system_message="You are a result aggregator. Synthesize worker agent results into a clear, actionable response for the user. Be concise and structured.",
            )
            chat.with_model("gemini", "gemini-2.5-flash")
            prompt = f"""Original query: {job.original_query}

Strategy: {job.aggregation_strategy}

Worker results:
{results_text}

Synthesize these into a clear final response for the user."""

            response = await chat.send_message(UserMessage(text=prompt))
            draft = response.strip() if isinstance(response, str) else response.text.strip()

            # ==================== CONSENSUS COUNCIL ====================
            consensus = await self._consensus_check(job, draft, results_text)
            job.consensus = consensus

            if consensus["approved"]:
                return draft
            else:
                # Incorporate reviewer feedback and re-synthesize
                revision_prompt = f"""Your draft response was reviewed by a council of agents.

Original query: {job.original_query}
Your draft: {draft[:1000]}

Reviewer feedback:
{chr(10).join(consensus.get('feedback', []))}

Please revise your response addressing the feedback. Be concise."""

                chat2 = LlmChat(
                    api_key=EMERGENT_KEY,
                    session_id=f"swarm-rev-{job.id}",
                    system_message="You are a result aggregator revising based on peer review feedback.",
                )
                chat2.with_model("gemini", "gemini-2.5-flash")
                revision = await chat2.send_message(UserMessage(text=revision_prompt))
                revised = revision.strip() if isinstance(revision, str) else revision.text.strip()
                return revised

        except Exception as e:
            return f"## Swarm Results\n{results_text}"

    async def _consensus_check(self, job: SwarmJob, draft: str, worker_results: str) -> Dict:
        """
        Consensus Council — Two independent reviewer agents cross-check the draft.
        Both must approve (or agree on issues) before the response is marked as verified.
        Returns: {approved: bool, votes: [...], feedback: [...], confidence: float}
        """
        reviewer_prompt = f"""You are a Consensus Reviewer on a Council of Agents. Your job is to critically evaluate a draft response produced by a swarm of worker agents.

Original user query: {job.original_query}

Worker results summary:
{worker_results[:1500]}

Draft response to evaluate:
{draft[:1500]}

Evaluate on these criteria:
1. ACCURACY: Does the response correctly reflect the worker results?
2. COMPLETENESS: Does it address all aspects of the original query?
3. COHERENCE: Is the response well-structured and clear?
4. HONESTY: Does it acknowledge limitations or gaps in the data?

Respond with ONLY valid JSON:
{{
    "vote": "approve" or "reject",
    "confidence": 0.0 to 1.0,
    "issues": ["list of specific issues found, empty if none"],
    "suggestions": ["list of improvements, empty if none"]
}}"""

        reviews = []
        # Spawn 2 independent reviewers in parallel
        async def run_reviewer(reviewer_id: int):
            try:
                chat = LlmChat(
                    api_key=EMERGENT_KEY,
                    session_id=f"swarm-review-{job.id}-r{reviewer_id}",
                    system_message="You are a critical peer reviewer. Evaluate responses honestly and thoroughly.",
                )
                chat.with_model("gemini", "gemini-2.5-flash")
                resp = await chat.send_message(UserMessage(text=reviewer_prompt))
                text = resp.strip() if isinstance(resp, str) else resp.text.strip()
                if "```json" in text:
                    text = text.split("```json")[1].split("```")[0].strip()
                elif "```" in text:
                    text = text.split("```")[1].split("```")[0].strip()
                return json.loads(text)
            except Exception as e:
                return {"vote": "approve", "confidence": 0.5, "issues": [str(e)], "suggestions": []}

        results = await asyncio.gather(run_reviewer(1), run_reviewer(2))
        reviews = results

        # Tally votes
        approvals = sum(1 for r in reviews if r.get("vote") == "approve")
        avg_confidence = sum(r.get("confidence", 0.5) for r in reviews) / len(reviews)

        # Collect all feedback
        all_issues = []
        all_suggestions = []
        for r in reviews:
            all_issues.extend(r.get("issues", []))
            all_suggestions.extend(r.get("suggestions", []))

        # Consensus requires majority approval AND average confidence >= 0.6
        approved = approvals >= 2 or (approvals >= 1 and avg_confidence >= 0.7)

        feedback = []
        if all_issues:
            feedback.append("Issues found: " + "; ".join(all_issues[:5]))
        if all_suggestions:
            feedback.append("Suggestions: " + "; ".join(all_suggestions[:5]))

        return {
            "approved": approved,
            "votes": [{"reviewer": i + 1, "vote": r.get("vote"), "confidence": r.get("confidence", 0)} for i, r in enumerate(reviews)],
            "feedback": feedback,
            "confidence": round(avg_confidence, 2),
            "issues_count": len(all_issues),
        }

    def get_job(self, job_id: str) -> Optional[SwarmJob]:
        return self.jobs.get(job_id)

    def list_jobs(self) -> List[Dict]:
        return [j.to_dict() for j in self.jobs.values()]

    def get_status(self) -> Dict:
        active = sum(1 for j in self.jobs.values() if j.status in ("planning", "executing", "aggregating"))
        return {
            "total_jobs": len(self.jobs),
            "active_jobs": active,
            "workers_available": list(WORKER_PROFILES.keys()),
        }


# Singleton
swarm = SwarmOrchestrator()
