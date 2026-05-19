# SnowballBot API Documentation

Base URL: `http://localhost:8000`

All POST endpoints accept `Content-Type: application/json`.

---

## Skills Registry

### GET /api/skills/modules
List all 25 registered skills with metadata.

**Response:**
```json
{
  "total": 25,
  "ready": 22,
  "skills": [
    {
      "id": "text_triage",
      "name": "Text Triage",
      "description": "...",
      "category": "communication",
      "needs_config": [],
      "badge": "NEW"
    }
  ]
}
```

---

## Core Agent

### POST /api/chat
Send a message to the autonomous agent.

**Body:** `{ "message": "string", "session_id": "string" }`

### GET /api/memory
Get all agent memory entries.

### POST /api/memory
Add a memory entry.

### GET /api/suggestions
Get proactive agent suggestions based on context.

---

## Reasoning Skills

### POST /api/skills/intent/predict
**Level 1: Intentionality Prediction**

Predict user intent before responding.

**Body:** `{ "message": "string" }`

**Response:**
```json
{
  "prediction_id": "abc123",
  "primary_intent": "action",
  "secondary_intent": "question",
  "intent_scores": { "action": 0.65, "question": 0.25, "social": 0.1 },
  "urgency": "high",
  "confidence": 0.65,
  "recommended_style": "confirmatory + brief — do the thing, summarize what was done"
}
```

Intents: `question | action | learning | social | complaint | creative`
Urgency: `high | medium | low`

---

### POST /api/skills/temporal/analyze
**Level 4: Temporal Reasoning**

Analyze a task for deadline and priority.

**Body:** `{ "task": "string", "context": "string (optional)" }`

**Response:**
```json
{
  "task_id": "abc123",
  "deadline_days": 1.0,
  "urgency_score": 0.95,
  "importance_score": 0.8,
  "priority_score": 0.82,
  "deadline_label": "tomorrow",
  "recommendation": "Handle today — High priority, don't defer."
}
```

### POST /api/skills/temporal/rank
Rank multiple tasks by priority.

**Body:** `{ "tasks": ["task 1 due tomorrow", "task 2 no rush"] }`

---

### POST /api/skills/cognitive/assess
**Level 11: Cognitive Load Management**

Assess user's mental bandwidth and get verbosity recommendation.

**Body:** `{ "message": "string", "message_history": ["..."] }`

**Response:**
```json
{
  "load_level": "high",
  "verbosity": "concise",
  "instruction": "Short paragraph. Core answer + 1 reason. Max 120 words.",
  "include_bullets": true,
  "include_examples": false
}
```

### GET /api/skills/cognitive/current
Get current verbosity setting.

### POST /api/skills/cognitive/override
Set verbosity manually.
**Body:** `{ "verbosity": "minimal|concise|normal|detailed" }`

### POST /api/skills/cognitive/reset
Reset to auto-detection.

---

## Problem Reverser

### POST /api/skills/reverser/analyze
Reverse-engineer root cause from external evidence.

**Body:**
```json
{
  "problem": "App is slow after 2pm",
  "observed_evidence": {
    "performance": ["CPU 85%", "RAM 90%"],
    "temporal": ["happens every afternoon"]
  },
  "context": "optional background"
}
```

### POST /api/skills/reverser/collect-evidence
Get recommended evidence to collect for a problem.

**Body:** `{ "problem": "string", "evidence_type": "all|performance|temporal|..." }`

### POST /api/skills/reverser/trace
Trace backwards from symptom through evidence to root cause.

**Body:** `{ "symptom": "string", "hypothesis": "string", "collected_evidence": ["..."] }`

### GET /api/skills/reverser/evidence-types
List all observable evidence categories.

### GET /api/skills/reverser/analyses?limit=20
Recent analyses.

---

## Ghidra Analyzer

### POST /api/skills/ghidra/analyze
Deep analysis of a code file.

**Body:** `{ "file_path": "backend/server.py", "deep": false }`

**Response:**
```json
{
  "analysis_id": "abc123",
  "analysis_type": "python_structure",
  "findings": {
    "functions": [{ "name": "analyze_file", "args": ["file_path", "deep"] }],
    "classes": [{ "name": "GhidraAnalyzerSkill", "methods": ["analyze_file", ...] }],
    "imports": ["ast", "json", "re"],
    "async_funcs": ["_llm"]
  },
  "complexity_score": 0.45,
  "risk_flags": [],
  "patterns_found": ["async_processing", "file_operations"],
  "recommendations": []
}
```

### POST /api/skills/ghidra/architecture
Map directory file structure.

**Body:** `{ "directory": ".", "recursive": true }`

### POST /api/skills/ghidra/find-pattern
Search codebase for regex pattern.

**Body:** `{ "pattern": "eval|exec", "directory": ".", "file_type": "*" }`

---

## Stewardship Layer (Governance)

### POST /api/skills/steward/evaluate
Evaluate if an action aligns with mission before execution.

**Body:**
```json
{
  "agent_id": "agent_001",
  "action": { "type": "send_email", "description": "...", "estimated_cost": 0.01 },
  "user_values": { "privacy": "critical" }
}
```

**Response:**
```json
{
  "status": "approved|flagged|blocked",
  "alignment_score": 0.96,
  "reason": "Passed all governance gates.",
  "checks": {
    "mission_alignment": { "pass": true, "score": 1.0, "flags": [] },
    "cost_feasibility": { "pass": true, "score": 1.0, "headroom_usd": 9.95 },
    "value_alignment": { "pass": true, "score": 0.85 },
    "safety_gates": { "pass": true, "score": 1.0 }
  }
}
```

### GET /api/skills/steward/audit?limit=50
Immutable audit trail of all governance decisions.

### GET /api/skills/steward/alignment-report
System health: are agents staying aligned?

### GET /api/skills/steward/operational-metrics
Cost status, budget headroom.

### GET /api/skills/steward/missions
All 5 mission statements (the constitution).

### GET /api/skills/steward/policies
Full governance policy document.

---

## Stewardship (Protective)

### POST /api/skills/protective/propose-destructive
Propose a destructive action. Returns what would be lost, requires user consent.

**Body:** `{ "action_type": "delete|overwrite|truncate|archive", "target": "path", "reason": "..." }`

### POST /api/skills/protective/execute-destructive
Execute ONLY after user confirms.

**Body:** `{ "action_id": "...", "user_confirmed": true, "user_message": "..." }`

### GET /api/skills/protective/trash?limit=20
Items moved to trash (recoverable).

### POST /api/skills/protective/recover
Restore from trash.

**Body:** `{ "trash_name": "file_abc123", "restore_path": "original/path" }`

### GET /api/skills/protective/continuity
Agent's memory state across sessions.

### PUT /api/skills/protective/continuity
Update continuity/memory.

**Body:** `{ "active_projects": [...], "memory_checkpoints": {...} }`

### GET /api/skills/protective/destructive-log?limit=50
Full audit trail of destructive action proposals/executions.

---

## Integration Pipeline

### POST /api/pipeline/diagnose
**Problem Reverser → Ghidra chained analysis.**

Observe a problem, identify the source file, then deep-analyze it.

**Body:**
```json
{
  "problem": "API endpoint is slow",
  "observed_evidence": { "performance": ["latency 2s", "CPU 80%"] },
  "target_file": "backend/server.py"
}
```

**Response:**
```json
{
  "pipeline_id": "...",
  "step_1_reverser": { "root_cause_hypothesis": "...", "confidence": 0.8 },
  "step_2_ghidra": { "functions": [...], "risk_flags": [], "complexity_score": 0.6 },
  "combined_recommendation": "...",
  "next_actions": [...]
}
```

---

## Reference Skills

### POST /api/skills/bible/search
**Body:** `{ "query": "john 3:16" }`

### GET /api/skills/bible/daily?seed=
Daily meditation verse.

### GET /api/skills/bible/books
All books with chapter counts.

### POST /api/skills/dictionary/define
**Body:** `{ "word": "serendipity" }`

### GET /api/skills/dictionary/words
All known words.

### POST /api/skills/dictionary/search
**Body:** `{ "keyword": "luck" }`

### POST /api/skills/thesaurus/synonyms
**Body:** `{ "word": "happy", "intensity": "exact|stronger|weaker" }`

### POST /api/skills/thesaurus/antonyms
**Body:** `{ "word": "happy" }`

### POST /api/skills/thesaurus/suggest
**Body:** `{ "word": "tired", "context": "formal|casual|strong|neutral" }`

---

## Marketplace Skills

All marketplace skills share this pattern:

| Skill | Prefix | Key Endpoint |
|-------|--------|--------------|
| Text Triage | `/api/skills/triage` | POST `/triage` |
| Calendar Cleric | `/api/skills/calendar` | POST `/schedule` |
| Receipt Rabbi | `/api/skills/receipt` | POST `/scan` |
| Voicemail Vandal | `/api/skills/voicemail` | POST `/transcribe` |
| Deal Doula | `/api/skills/deal` | POST `/analyze` |
| Lease Lawyer | `/api/skills/lease` | POST `/review` |
| Gym Ghost | `/api/skills/gym` | POST `/log` |
| DM Deflector | `/api/skills/dm` | POST `/analyze` |
| Tab Taxidermist | `/api/skills/tabs` | POST `/revive` |
| Fridge Forensics | `/api/skills/fridge` | POST `/analyze` |

All skills have a GET `/stats` endpoint.

---

## Error Responses

```json
{ "detail": "Error description" }   // 400/404/500
{ "error": "Error description" }    // Skill-level errors
```

---

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `GROQ_API_KEY` | Recommended | LLM for agent reasoning |
| `EMERGENT_LLM_KEY` | Fallback | Alternative LLM |
| `MONGODB_URL` | Required | Database connection |
| `DB_NAME` | Optional | Database name (default: snowdrift) |
| `TELEGRAM_BOT_TOKEN` | Optional | Voicemail Vandal |
| `EBAY_APP_ID` | Optional | Deal Doula marketplace |
| `NIM_API_KEY` | Optional | Advanced vision models |
