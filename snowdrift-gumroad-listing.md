# 🏔️ SnowDrift — Self-Healing Android AI Agent

**The only Android AI agent that heals itself when your phone updates.**

SnowDrift lives on your phone. It sees your screen, taps your buttons, reads your texts, and does the work you don't want to — all through Android's accessibility layer. When your phone updates and breaks things, SnowDrift fixes itself. No other agent does this.

## What Makes SnowDrift Different

- **🩹 Self-Healing Engine** — When Android updates break accessibility hooks, SnowDrift detects the failure, diagnoses the breakage, and patches itself automatically. Your agent stays alive through OS updates.
- **📱 Full Phone Control** — Accessibility service gives SnowDrift real screen reading, tap automation, and app navigation. Not chat — *action*.
- **🧠 Sovereign Memory** — Your data stays on your device. Memory tree with branches, leaves, and roots. No cloud dependency for recall.
- **🛡️ Stewardship Layer** — Protective governance prevents destructive actions. SnowDrift refuses to do things that would harm your data or device.
- **🏛️ Council (NEW)** — 3-stage multi-model debate. Ask a question, get Alpha/Beta/Gamma perspectives, then a synthesized verdict. The best answer, not just one answer.
- **⚡ 25 Built-in Skills** — Price monitoring, DM management, workout tracking, meal planning, code analysis, and 20 more. Each one works offline.
- **🔌 LLM-Agnostic** — Works with OpenAI, Anthropic, Gemini, Ollama, or Groq. Swap models without changing your setup.
- **🔄 Chaquopy-Powered** — Python backend running natively on Android via Chaquopy. No cloud round-trips for core logic.

## Skills Included (8 Free / 17 Premium)

### Free Core Skills
- `memory` — Sovereign recall with tree-structured persistence
- `chat` — LLM-powered conversation with any provider
- `self_healing` — Auto-diagnosis and repair on OS updates
- `stewardship_layer` — Governance and safety guardrails
- `stewardship_protective` — Destructive action prevention
- `swarm` — Multi-agent orchestration
- `ghostwright` — Writing and content generation
- `nim_router` — Smart model routing per task

### Premium Skills ($2–5 each, or $12 for all)
- `council` — 3-stage multi-model debate (Alpha → Beta → Gamma → Verdict)
- `deal_doula` — Price monitoring and deal alerts
- `dm_deflector` — Auto-reply and filter incoming DMs
- `gym_ghost` — Workout tracking and personal records
- `fridge_forensics` — Inventory tracking and meal ideas
- `calendar_cleric` — Focus block scheduling
- `receipt_rabbi` — Expense tracking for freelancers
- `tab_taxidermist` — Browser tab management
- `ghidra_analyzer` — Code security analysis
- `problem_reverser` — Outside-in problem solving
- `key_rotator` — API key rotation automation
- `hobby` — Context-aware hobby suggestions
- `lease_lawyer` — Lease term analysis
- `voicemail_vandal` — Voicemail transcription and action
- `daisy_chain` — Chained skill execution pipelines
- `snowball_swarm` — Distributed agent coordination
- `async_messaging` — Async message queue processing
- Plus 3 reasoning skills (cognitive, intentional, temporal)

## Architecture

```
┌─────────────────────────────────────────────┐
│                 Android APK                  │
│  ┌──────────┐  ┌──────────┐  ┌────────────┐│
│  │ Kotlin   │  │ React    │  │ Python     ││
│  │ UI Layer │  │ Native   │  │ Chaquopy   ││
│  │ (Access.)│  │ Faces    │  │ Backend    ││
│  └────┬─────┘  └────┬─────┘  └─────┬──────┘│
│       │              │              │       │
│       └──────────────┼──────────────┘       │
│                      │                      │
│           ┌──────────▼──────────┐           │
│           │  Sovereign Memory   │           │
│           │  (On-Device Tree)   │           │
│           └──────────┬──────────┘           │
│                      │                      │
│           ┌──────────▼──────────┐           │
│           │  Self-Healing Engine│           │
│           │  (LTS Monitor)      │           │
│           └────────────────────┘           │
└─────────────────────────────────────────────┘
```

## Quick Start

### Self-Hosted (Free, Forever)

1. Clone the repo: `git clone https://github.com/snowball1452-lgtm/snowdrift.git`
2. Set up your `.env` with your LLM API keys
3. Build the APK: `cd android && ./gradlew assembleRelease`
4. Install on your phone
5. Grant accessibility permissions
6. Talk to SnowDrift

### ☁️ SnowDrift Cloud ($5/mo)

Don't want to self-host? We run the Python backend for you.
Just install the APK and point it at your cloud relay.
No local server needed. Self-healing still works — the cloud just handles the Python runtime.

## Licensing

SnowDrift is **MIT** — maximum freedom.

**What this means:**
- ✅ Use it, modify it, fork it, sell it, embed it — no restrictions
- ✅ Commercial use is fully allowed, no separate license needed
- ✅ No copyleft obligations — your modifications can be open or closed
- ✅ The only requirement: keep the copyright notice

**Why MIT?**
Because some kid in 20 years should be able to download this, build some wild cyberpunk version, and run it freely. No gates. No confusion. Just code that outlives the author.

## Security Notice

⚠️ **Your keys are your keys.** SnowDrift never sends your API keys, memories, or personal data to any server you don't configure. All skill data (workouts, DMs, browsing history) stays on your device in the `backend/.skillname/` directories.

## Built By

Chad Snowball — [GitHub](https://github.com/snowball1452-lgtm/snowdrift) | [Gumroad](https://snowball.gumroad.com)

---

*If SnowDrift breaks, it fixes itself. If your phone updates, it adapts. That's the promise.*