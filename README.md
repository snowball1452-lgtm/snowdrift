# SnowDrift — On-Device Android AI Agent

> A full ReAct agent that runs **completely on your phone**. No cloud. No subscription. No API required.  
> 25MB APK. Python brain embedded via Chaquopy. Ollama-powered inference.

---

## What This Actually Is

Most "AI apps" are thin wrappers around an API call. SnowDrift is different.

The entire agent loop — memory, reasoning, skills, self-healing, swarm orchestration — runs as a live Python FastAPI server **inside the APK**, on your device. When you're offline, it still works. When you're on WiFi, it can route to a local Ollama instance or cloud LLMs. You own the stack.

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                     Android APK                         │
│                                                         │
│  ┌──────────────┐    ┌───────────────────────────────┐  │
│  │  Kotlin UI   │◄──►│   Chaquopy Python Runtime     │  │
│  │  (Chat UI,   │    │                               │  │
│  │  Accessibility│   │  ┌─────────────────────────┐  │  │
│  │  Service,    │    │  │  FastAPI Daemon (:8001)  │  │  │
│  │  Voice,      │    │  │  • ReAct Agent Loop      │  │  │
│  │  Phone Acts) │    │  │  • Sovereign Memory      │  │  │
│  └──────────────┘    │  │  • Self-Healing Engine   │  │  │
│                      │  │  • Swarm Orchestrator    │  │  │
│                      │  │  • 29 Skills             │  │  │
│                      │  │  • L1/L11 Reasoning      │  │  │
│                      │  │  • Stewardship Gate      │  │  │
│                      │  └─────────────────────────┘  │  │
│                      └───────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
         │
         ▼
  Local Ollama (WiFi/USB)  OR  Cloud LLM (OpenAI/Anthropic/Gemini)
```

---

## Features

### 🧠 Agent Intelligence
- **ReAct Agent Loop** — Think → Act → Observe, up to 5 iterations per message
- **L1 Intentionality Prediction** — Predicts *why* you sent the message (question / action / learning / social) before responding
- **L11 Cognitive Load Manager** — Detects if you're busy and adapts verbosity automatically. Short answer when you're slammed, full explanation when you want depth
- **Stewardship Layer** — Constitutional governance gate on every action. Mission alignment, cost feasibility, safety checks before anything executes

### 🔮 Memory
- **Sovereign Memory** — Blake3-sealed, content-addressed memory with Gaussian relevance scoring and Merkle tree integrity proofs. Your memories are cryptographically yours
- **Sovereign Cognitive Cell** — Perception loop that stores and retrieves observations with semantic similarity scoring
- **Persistent across restarts** — Memory survives app kills via MongoDB or local file fallback

### 🛠 Skills (29 built-in)
| Category | Skills |
|----------|--------|
| **Intelligence** | Problem Reverser, Ghidra Analyzer, Hobby Detector |
| **Reasoning** | Intentionality (L1), Temporal (L4), Cognitive Load (L11) |
| **Communication** | GutPunch Messaging, Text Triage, DM Deflector, Voicemail Vandal |
| **Productivity** | Calendar Cleric, Tab Taxidermist |
| **Finance** | Receipt Rabbi, Deal Doula, FlipBot |
| **Reference** | Bible, Dictionary, Thesaurus |
| **Home & Health** | Fridge Forensics, Gym Ghost |
| **Legal** | Lease Lawyer |
| **Browser** | Daisy Chain (CDP observer) |
| **Media** | NIM Image Router (FLUX, SD 3.5) |
| **Infrastructure** | Key Rotator, Stewardship Layer, Stewardship Protective, Snowball Swarm |

### ⚡ Swarm Mode
- **Snowball Swarm** — Decomposes complex tasks into parallel subtasks across 10 predefined agent roles
- Blake3 witness chain — every sub-result is cryptographically stamped
- Model-agnostic — works with any Ollama model or cloud LLM

### 🔧 Self-Healing
- Monitors its own server process
- Auto-restarts with exponential backoff on crashes
- Import failures are isolated — one broken skill never takes down the daemon

### 📱 Android-Native
- **Accessibility Service** — Watches the screen, enables cross-app automation
- **Phone Actions** — Set alarms, send SMS, make calls, open apps, copy clipboard
- **Voice** — Voice input to agent
- **WebSocket bridge** — Real-time UI updates as the agent thinks

---

## LLM Providers

| Provider | How |
|----------|-----|
| **Ollama** (default) | Point at `http://localhost:11434` — fully offline on your home network |
| **OpenAI** | GPT-4o, GPT-5 — add key in settings |
| **Anthropic** | Claude Sonnet/Haiku — add key in settings |
| **Gemini** | 2.5 Pro/Flash — add key in settings |

---

## Build Instructions

### Prerequisites
- Android Studio (includes JDK — use the bundled JBR at `Android Studio/jbr`)
- Android SDK (API 26+)
- Python 3.10 (for Chaquopy build host — Windows or Mac)

### Steps

```bash
git clone https://github.com/snowball1452-lgtm/snowdrift
cd snowdrift/android

# Copy and fill in local.properties
cp local.properties.template local.properties
# Edit local.properties — set sdk.dir and keystore paths

# Set JAVA_HOME to Android Studio's bundled JRE
export JAVA_HOME="/path/to/Android Studio/jbr"   # Mac/Linux
# set JAVA_HOME=C:\Program Files\Android\Android Studio\jbr  # Windows

./gradlew assembleRelease
```

APKs land in `app/build/outputs/apk/release/`.  
Sideload `app-arm64-v8a-release.apk` on any ARM64 Android device.

### Dep Pins (why they matter)
The Chaquopy build host compiles Python wheels on your machine. Three packages fail if unpinned:
- `fastapi==0.110.3` — 0.111.0 adds fastapi-cli → orjson (Rust, no ARM wheel)
- `uvicorn==0.29.0` (plain, no `[standard]`) — avoids uvloop which hard-fails on Windows build hosts
- `pydantic==1.10.21` — v2 requires pydantic-core (Rust); v1 is pure Python, identical API for this codebase

These are already locked in `app/build.gradle`. Don't change them without testing a full build.

---

## Project Structure

```
android/
├── app/
│   ├── build.gradle                    # Chaquopy config + dep pins
│   └── src/main/
│       ├── java/com/snowdrift/           # Kotlin — UI, services, Kotlin↔Python bridge
│       │   ├── MainActivity.kt
│       │   ├── PythonDaemonManager.kt  # Launches Python in-process (NOT subprocess)
│       │   ├── SnowDriftAccessibilityService.kt
│       │   ├── PhoneActions.kt
│       │   └── ...
│       └── python/                     # Python — agent brain
│           ├── server.py               # FastAPI app, ReAct loop, all API routes
│           ├── daemon_launcher.py      # In-process uvicorn launcher
│           ├── sovereign_memory_prod.py
│           ├── sovereign_cognitive_cell.py
│           ├── self_healing.py
│           ├── swarm.py
│           ├── ghostwright.py          # Android shim (Playwright unavailable on ARM)
│           ├── emergentintegrations/   # Stub — routes to Ollama on-device
│           └── skills/                 # 29 skill modules
│               ├── __init__.py         # SKILL_REGISTRY
│               ├── stewardship_layer.py
│               ├── reasoning_intentionality.py
│               ├── reasoning_cognitive_load.py
│               ├── snowball_swarm.py
│               └── ... (25 more)
backend/
├── server.py                           # Same agent, cloud-hosted (Replit/Railway)
└── skills/                             # Shared skill source
```

---

## API Endpoints

The Python daemon runs at `http://127.0.0.1:8001/api/`

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/health` | Daemon status |
| GET | `/api/skills` | All skills + active reasoning layers |
| POST | `/api/chat` | Send message, get agent response |
| GET | `/api/conversations` | Conversation history |
| POST | `/api/settings` | Update LLM provider/model |
| GET | `/api/memory/query` | Query sovereign memory |
| POST | `/api/agents/register` | Register a connected agent node |
| WS | `/ws/{conversation_id}` | Real-time streaming |

---

## Why It Works Offline

Chaquopy embeds a full CPython 3.10 interpreter as compiled `.so` libraries inside the APK. There's no subprocess call — the Python daemon runs in a dedicated thread via `uvicorn.Server(config).serve()` on its own asyncio event loop. The Kotlin side communicates via localhost HTTP. No JNI marshaling overhead, no IPC, just regular HTTP on loopback.

When Ollama is running on the same WiFi network (or via USB tethering), inference is fully local. The app works with zero internet connectivity.

---

## License

MPL-2.0
