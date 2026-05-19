# SnowballBot Architecture

## System Overview

SnowballBot is an autonomous AI agent with a phone-first Expo React Native frontend, FastAPI backend, and a 25-skill module system governed by a Stewardship Layer.

```
┌─────────────────────────────────────────────────────────────────────┐
│                        USER / PHONE                                  │
└──────────────────────────────┬──────────────────────────────────────┘
                               │ HTTPS
┌──────────────────────────────▼──────────────────────────────────────┐
│              EXPO REACT NATIVE FRONTEND (Port 5000)                  │
│  index.tsx (chat) │ skills.tsx │ stewardship.tsx │ ghidra.tsx        │
│  onboarding.tsx   │ settings.tsx │ conversations.tsx                 │
└──────────────────────────────┬──────────────────────────────────────┘
                               │ Axios HTTP
┌──────────────────────────────▼──────────────────────────────────────┐
│                  FASTAPI BACKEND (Port 8000)                          │
│                                                                       │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │                    AGENT CORE (server.py)                    │    │
│  │                                                               │    │
│  │  POST /api/chat                                               │    │
│  │    └── parse_intent (Intentionality L1)                       │    │
│  │    └── assess_load (Cognitive Load L11)                       │    │
│  │    └── get_agent_context (memory + skills + state)            │    │
│  │    └── LLM ReAct loop (Groq/Emergent)                         │    │
│  │    └── process_agent_action (25 skills available)             │    │
│  │    └── steward.evaluate_action (governance gate)              │    │
│  │    └── return response                                         │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                                                                       │
│  ┌──────────────┐  ┌────────────────┐  ┌────────────────────────┐  │
│  │  STEWARDSHIP │  │    REASONING   │  │       PIPELINE         │  │
│  │    LAYER     │  │    ENGINE      │  │                        │  │
│  │              │  │                │  │  /api/pipeline/diagnose │  │
│  │ ┌──────────┐ │  │ L1 Intent      │  │  Problem Reverser      │  │
│  │ │Governance│ │  │ L4 Temporal    │  │    → Ghidra Analyzer   │  │
│  │ │ 5 missions│ │  │ L11 Cognitive  │  │    → Action Plan       │  │
│  │ │ Audit log│ │  │                │  │                        │  │
│  │ │ Cost mgmt│ │  │ (Levels 2-3,   │  │                        │  │
│  │ └──────────┘ │  │  5-10, 12 TBD) │  │                        │  │
│  │ ┌──────────┐ │  └────────────────┘  └────────────────────────┘  │
│  │ │Protective│ │                                                     │
│  │ │ Trash    │ │  ┌────────────────────────────────────────────┐   │
│  │ │ Continuity│ │  │              25 SKILL MODULES              │   │
│  │ └──────────┘ │  │                                            │   │
│  └──────────────┘  │  INFRASTRUCTURE (4)    REASONING (3)       │   │
│                     │  ├─ agent_os            ├─ problem_reverser │   │
│                     │  ├─ stewardship_layer   ├─ ghidra_analyzer  │   │
│                     │  ├─ stewardship_protect ├─ reasoning_*      │   │
│                     │  └─ key_rotator                             │   │
│                     │                                            │   │
│                     │  MEMORY (1)            AGENTS (1)          │   │
│                     │  └─ sovereign_memory   └─ snowball_swarm   │   │
│                     │                                            │   │
│                     │  COMMUNICATION (4)     INTELLIGENCE (1)    │   │
│                     │  ├─ async_messaging     └─ nim_router       │   │
│                     │  ├─ dm_deflector                           │   │
│                     │  ├─ voicemail_vandal                       │   │
│                     │  └─ flipbot                                │   │
│                     │                                            │   │
│                     │  MARKETPLACE (10)      REFERENCE (3)       │   │
│                     │  ├─ text_triage         ├─ reference_bible  │   │
│                     │  ├─ calendar_cleric     ├─ reference_dict   │   │
│                     │  ├─ receipt_rabbi       └─ reference_thes   │   │
│                     │  ├─ deal_doula                              │   │
│                     │  ├─ lease_lawyer                           │   │
│                     │  ├─ gym_ghost                              │   │
│                     │  ├─ tab_taxidermist                        │   │
│                     │  └─ fridge_forensics                       │   │
│                     └────────────────────────────────────────────┘   │
└───────────────────────────────────────────────────────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────────────────┐
│                          DATA LAYER                                   │
│  MongoDB (moltbot DB)  │  .stewardship/  │  .reasoning_*/           │
│  - messages            │  - audit.jsonl  │  - predictions.jsonl     │
│  - memory              │  - trash/       │  - tasks.jsonl           │
│  - agent_state         │  - continuity   │  - state.json            │
└──────────────────────────────────────────────────────────────────────┘
```

---

## Agent Decision Loop

Every user message flows through this sequence:

```
1. Receive message
       │
2. Intentionality Prediction (Level 1)
   → Classify: question | action | learning | social | complaint | creative
   → Urgency: high | medium | low
       │
3. Cognitive Load Assessment (Level 11)
   → Load: low | medium | high | critical
   → Verbosity: detailed | normal | concise | minimal
       │
4. Build Agent Context
   → Recent memory (MongoDB)
   → Available skills (25)
   → Continuity state (.stewardship/continuity.json)
   → Current verbosity instruction
       │
5. LLM ReAct Loop (Groq llama-3.3-70b or Emergent fallback)
   → Think: what action is needed?
   → Act: call skill or respond directly
   → Observe: what happened?
   → Repeat until done
       │
6. Stewardship Gate (if action is proposed)
   → Mission alignment check (5 missions)
   → Cost feasibility check
   → Value alignment check (user values)
   → Safety gates (loop detection, recursion depth)
   → APPROVED | FLAGGED | BLOCKED
       │
7. Execute approved action
       │
8. Log to audit trail
       │
9. Return response (adapted to cognitive load)
```

---

## Skill Registry

Skills are registered in `backend/skills/__init__.py`:

```python
SKILLS = {
    "skill_id": {
        "name": "Skill Name",
        "description": "...",
        "category": "infrastructure|memory|agents|...",
        "needs_config": [],  # empty = ready to use
        "icon": "ionicon-name",
        "agent_action": "skill_shortname",
        "badge": "NEW|HOT|FREE|CORE",
    }
}
```

The agent uses `agent_action` to match tool calls in the ReAct loop.

---

## Stewardship Architecture

The Stewardship Layer has two components:

**stewardship_layer.py** — Constitutional governance:
- 5 mission statements (the constitution)
- Action evaluation before execution
- Alignment scoring + status (approved/flagged/blocked)
- Cost tracking + budget enforcement
- Immutable audit log (cryptographically chained)

**stewardship_protective.py** — Caretaker core:
- Protected items list (never touched without consent)
- Destructive action proposal flow (propose → confirm → execute)
- Trash system (move instead of delete)
- Continuity state (agent memory across sessions)

---

## Skill Pattern

All skills follow this singleton pattern:

```python
class MySkill:
    def __init__(self):
        MY_DIR.mkdir(parents=True, exist_ok=True)
    
    async def _llm(self, prompt: str) -> str:
        """LLM call with Groq primary, Emergent fallback."""
        ...
    
    def my_action(self, input: str) -> dict:
        ...
    
    def get_stats(self) -> dict:
        ...

_instance = None
def get_my_skill() -> MySkill:
    global _instance
    if _instance is None:
        _instance = MySkill()
    return _instance
```

Files are stored in hidden dirs: `.skill_name/`

---

## Frontend Structure

```
frontend/app/
├── _layout.tsx          # Root layout + navigation
├── index.tsx            # Main chat screen
├── skills.tsx           # Skills/tools browser
├── stewardship.tsx      # Governance dashboard
├── ghidra.tsx           # Code analysis viewer
├── settings.tsx         # API keys + preferences
├── conversations.tsx    # Chat history
├── onboarding.tsx       # First-run wizard
├── agent_os.tsx         # Agent system status
└── heal.tsx             # Error recovery

frontend/src/
├── store/chatStore.ts   # Global state (Zustand)
├── hooks/useFaceStyle.ts # Face/theme system
└── components/
    ├── SnowballFace.tsx  # Animated agent face
    └── Waveform.tsx      # Audio visualizer
```

---

## Environment Variables

| Variable | Required | Purpose |
|----------|----------|---------|
| `GROQ_API_KEY` | Yes (for LLM) | Primary LLM (llama-3.3-70b) |
| `EMERGENT_LLM_KEY` | Fallback | Alternative LLM provider |
| `MONGODB_URL` | Yes | Database |
| `DB_NAME` | No | Database name (default: moltbot) |
| `TELEGRAM_BOT_TOKEN` | Optional | Voicemail Vandal feature |
| `EBAY_APP_ID` | Optional | Deal Doula marketplace |
| `NIM_API_KEY` | Optional | Advanced vision models |

---

## Data Flow: Problem Reverser → Ghidra Pipeline

```
POST /api/pipeline/diagnose
       │
       ├── Step 1: Problem Reverser
       │     └── Collect evidence categories
       │     └── Build hypothesis tree
       │     └── Identify root cause + confidence
       │     └── Recommend next evidence to collect
       │
       ├── Step 2: Ghidra Analyzer
       │     └── Analyze target_file (if provided)
       │     └── Extract functions, classes, imports
       │     └── Detect risk flags
       │     └── Estimate complexity
       │
       └── Step 3: Combined Recommendation
             └── Merge reverser hypothesis + ghidra findings
             └── Generate prioritized action list
             └── Return pipeline_id + full analysis
```

---

## Reasoning Levels: Implementation Status

| Level | Name | Status |
|-------|------|--------|
| 1 | Intentionality Prediction | ✅ Implemented |
| 2 | Consequentialist Reasoning | ⏳ Phase 2 |
| 3 | Meta-Cognition | ⏳ Phase 3 |
| 4 | Temporal Reasoning | ✅ Implemented |
| 5 | Causal Reasoning | ⏳ Phase 2 |
| 6 | Counterfactual Reasoning | ⏳ Phase 3 |
| 7 | Analogical Reasoning | ⏳ Phase 2 |
| 8 | Abductive Reasoning | ⏳ Phase 3 |
| 9 | Recursive Goal Decomposition | ⏳ Phase 4 |
| 10 | Value Alignment | ⏳ Phase 4 |
| 11 | Cognitive Load Management | ✅ Implemented |
| 12 | Meta-Learning | ⏳ Phase 4 |
