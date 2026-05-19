# SnowballBot: 12 Advanced Reasoning Levels

## Overview

Most AI agents execute: `CAPABILITY → OUTPUT → DONE`

SnowballBot adds reasoning layers: `CAPABILITY → SHOULD I? → IS THIS SAFE? → WHO DOES THIS AFFECT? → OUTPUT`

The 12 reasoning levels define a progression from basic intent detection to full meta-learning.

---

## ✅ Phase 1 — Implemented (Quick Wins)

### Level 1: Intentionality Prediction
**File:** `backend/skills/reasoning_intentionality.py`
**Endpoint:** `POST /api/skills/intent/predict`

**What:** Predicts WHY the user is sending a message before responding.
**Why:** Knowing intent leads to dramatically more relevant responses.

**Intent Types:**
- `question` — User wants information or explanation
- `action` — User wants something done
- `learning` — User wants to understand a concept deeply
- `social` — Greeting, thanks, casual conversation
- `complaint` — Something is broken or frustrating
- `creative` — User wants generation, brainstorming, drafting

**How it works:**
1. Parse message for structural signals (starts with "what/how/can you"?)
2. Scan for keyword signals ("urgent", "explain", "create", etc.)
3. Score each intent type
4. Normalize scores to get probability distribution
5. Return primary + secondary intent with confidence

**Example:**
```
Input: "Can you quickly send the report to John?"
Output: {
  primary_intent: "action",
  urgency: "high",  // "quickly" detected
  confidence: 0.71,
  recommended_style: "confirmatory + brief — do it, then summarize"
}
```

**Integration Point:** Called at the start of every `/api/chat` request.

---

### Level 4: Temporal Reasoning
**File:** `backend/skills/reasoning_temporal.py`
**Endpoint:** `POST /api/skills/temporal/analyze`

**What:** Understands deadlines, urgency, and scheduling constraints.
**Why:** Without temporal reasoning, agent treats "urgent" and "whenever" identically.

**Priority Formula:**
```
priority = (importance × urgency) / log(deadline_days + 1)
```

**Deadline Detection (examples):**
- "today" → 0 days
- "tomorrow" → 1 day
- "in 3 hours" → 0.125 days
- "this week" → 5 days
- "eventually" → 90 days

**Importance Signals:**
- "critical", "must" → 0.85–1.0
- "important", "need to" → 0.7–0.8
- "should" → 0.5
- "could", "might" → 0.25–0.3

**Recommendations:**
- Priority > 0.8 → "HANDLE NOW — Drop other tasks"
- Priority > 0.6 → "Handle today"
- Priority > 0.4 → "Schedule this week"
- Priority ≤ 0.2 → "Park it"

**Example:**
```
Input: "I urgently need to review the lease contract by tomorrow morning"
Output: {
  deadline_days: 1.0,
  urgency_score: 0.95,
  importance_score: 0.9,
  priority_score: 0.82,
  recommendation: "Handle today — High priority, don't defer."
}
```

**Integration Point:** Used for task ranking and scheduling decisions.

---

### Level 11: Cognitive Load Management
**File:** `backend/skills/reasoning_cognitive_load.py`
**Endpoint:** `POST /api/skills/cognitive/assess`

**What:** Detects user's mental bandwidth and adapts response verbosity.
**Why:** An over-eager agent information-dumps on a user who just needs a quick answer.

**Load Levels:**
- `critical` → Minimal (1-2 sentences, max 40 words)
- `high` → Concise (short paragraph, max 120 words)
- `medium` → Normal (answer + context + example, max 300 words)
- `low` → Detailed (full explanation with alternatives, max 700 words)

**Detection Signals:**

*High load (user is busy):*
- Keywords: "quick question", "briefly", "tldr", "in a rush"
- Behavior: Short messages, many in quick succession

*Low load (user wants depth):*
- Keywords: "explain in detail", "walk me through", "deep dive"
- Behavior: Long messages, follow-up questions asking for more

**Verbosity Styles:**
```
minimal:  "1-2 sentences. Essential answer only. Max 40 words."
concise:  "Short paragraph. Core answer + 1 reason. Max 120 words."
normal:   "Balanced. Answer + context + example. Max 300 words."
detailed: "Full explanation with reasoning + examples. Max 700 words."
```

**Example:**
```
Input: "quick question, tldr version of the lease review?"
Output: {
  load_level: "high",
  verbosity: "concise",
  instruction: "Short paragraph. Core answer + 1 reason. Max 120 words."
}
```

---

## ⏳ Phase 2 — Planned (Medium Effort)

### Level 2: Consequentialist Reasoning
**What:** Simulates consequences of actions BEFORE executing them.

**How:**
```python
def evaluate_consequences(action, context) -> dict:
    risks = identify_risks(action)       # What could go wrong?
    rewards = identify_rewards(action)   # What's the upside?
    alternatives = generate_alternatives(action)  # Other options?
    
    if risks > THRESHOLD:
        return {"decision": "confirm_with_user", "risks": risks}
    return {"decision": "proceed", "rationale": rewards}
```

**Example:**
```
Action: "Send $500 payment to contact ID xyz"
Agent: "xyz is not in your known contacts. Risk: fraud. Confirm?"
```

---

### Level 5: Causal Reasoning
**What:** Asks "Why?" recursively to find root causes, not just symptoms.

**How:**
```python
def causal_chain(observation) -> list:
    causes = []
    current = observation
    while not is_root_cause(current):
        cause = ask_why(current)
        causes.append(cause)
        current = cause
    return causes
```

**Example:**
```
Observation: "User can't focus"
Why? → Attention fragmented
Why? → 47 Slack pings in 2 hours
Why? → No focus time blocked
Root cause: Calendar management / communication protocols
```

---

### Level 7: Analogical Reasoning
**What:** Finds similar past situations and applies learned lessons.

**How:**
```python
def find_analogues(current_situation) -> list:
    memories = search_memory(current_situation)
    return sorted(memories, key=lambda m: similarity_score(m, current_situation))
```

**Example:**
```
Current: "User stuck on difficult project"
Memory: "3 months ago, same pattern → 30-min walk helped"
Agent: "Last time you were this stuck, a break helped. Try it?"
```

---

## ⏳ Phase 3 — Advanced

### Level 3: Meta-Cognition (Thinking About Thinking)
Agent tracks its own confidence and flags uncertainty.

```python
def confidence_check(response, evidence) -> float:
    # Agent evaluates quality of its own reasoning
    return uncertainty_score
```

### Level 6: Counterfactual Reasoning
Agent explores A/B/C alternatives before committing.

```python
def explore_scenarios(situation) -> list:
    return [
        {"path": "A", "outcome": predict_outcome(A), "probability": 0.7},
        {"path": "B", "outcome": predict_outcome(B), "probability": 0.3},
    ]
```

### Level 8: Abductive Reasoning
Given incomplete data, infer the most likely explanation.

```python
def best_explanation(observations) -> dict:
    hypotheses = generate_hypotheses(observations)
    return max(hypotheses, key=lambda h: posterior_probability(h, observations))
```

---

## ⏳ Phase 4 — Expert

### Level 9: Recursive Goal Decomposition
Break vague goals into measurable sub-goals recursively.

```
"Grow my business" →
  Revenue → Sales, Pricing, Retention →
    Sales → Traffic, Conversion, AOV →
      Traffic → SEO, Ads, Referrals → ...
```

### Level 10: Value Alignment
Check all actions against user's stated values.

```python
def check_alignment(action, user_values) -> dict:
    violations = []
    for value in user_values:
        if contradicts(action, value):
            violations.append(value)
    return {"aligned": len(violations) == 0, "violations": violations}
```

### Level 12: Meta-Learning (Recursive Self-Improvement)
Agent learns how to learn better from its own history.

```python
def improve_learning_strategy(history) -> dict:
    success_rate = calculate_success_rate(history)
    if success_rate < THRESHOLD:
        new_strategy = evolve_strategy(history)
        return {"strategy": new_strategy, "reason": "past approach underperforming"}
```

---

## Integration Map

```
User Message
    │
    ▼
Level 1: Intentionality → (action, high urgency, confidence 0.8)
    │
    ▼
Level 11: Cognitive Load → (verbosity: concise, max 120 words)
    │
    ▼
Agent ReAct Loop
    │
    ▼ [if proposing action]
Level 4: Temporal → (priority: 0.82, handle today)
    │
    ▼ [if consequence uncertain]
Level 2: Consequentialist → (risk assessed, confirm? Y/N)
    │
    ▼
Stewardship Gate → (approved/flagged/blocked)
    │
    ▼
Response (adapted to cognitive load verbosity)
```

---

## Roadmap

| Phase | Levels | Effort | Timeline |
|-------|--------|--------|---------|
| 1 (done) | 1, 4, 11 | Low | Sprint 1 |
| 2 | 2, 5, 7 | Medium | Sprint 2-3 |
| 3 | 3, 6, 8 | High | Sprint 4-6 |
| 4 | 9, 10, 12 | Expert | Sprint 7-12 |
