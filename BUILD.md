# Building SnowDrift

Self-healing Android AI agent with sovereign memory, Chaquopy, and a 25-skill matrix.

## Where's the code?

The repo looks like it's mostly empty folders. It isn't — the skill code lives inside the Android asset tree because Chaquopy bundles Python directly into the APK.

| What you're looking for | Where it actually is |
|---|---|
| **All 22+ Python skills** (calendar_cleric, deal_doula, self_healing, sovereign_memory, etc.) | `android/app/src/main/python/skills/` |
| **Python daemon** (FastAPI server, memory sidecar) | `android/app/src/main/python/pythonserver.py`, `daemon_launcher.py`, `server.py` |
| **Kotlin app** (MainActivity, AccessibilityService, etc.) | `android/app/src/main/java/com/snowdrift/` |
| **Android manifest + permissions** | `android/app/src/main/AndroidManifest.xml` |
| **Backend state directories** (`.calendar_cleric/`, `.gym_ghost/`, etc.) | `backend/` — these are **runtime state**, not code. They're empty (`.gitkeep`) because the agent fills them when it runs. Gitignored content is excluded. |
| **Frontend** (chat UI, settings) | `frontend/` |
| **Architecture docs** | `ARCHITECTURE.md`, `API_DOCS.md`, `REASONING_LEVELS.md`, `STEWARDSHIP.md` |

## Prerequisites

- **Android Studio** (Hedgehog or newer)
- **Python 3.10** on the build host (for Chaquopy wheel compilation)
- **Java 17** (set in `compileOptions`)
- **Android SDK 34** (compileSdk / targetSdk)

## Setup

### 1. Clone and configure

```bash
git clone https://github.com/snowball1452-lgtm/snowdrift.git
cd snowdrift
cp local_properties.template android/local.properties
```

Edit `android/local.properties`:

```properties
# Your Android SDK path (Android Studio usually fills this):
sdk.dir=/path/to/Android/Sdk

# Python 3.10 for Chaquopy builds (must be 3.10, not 3.11+):
# macOS/Linux:
buildPython=python3
# Windows:
# buildPython=C\:/Users/you/AppData/Local/Programs/Python/Python310/python.exe
```

### 2. Generate a signing keystore

The release build expects `snowdrift.keystore` in the `android/` directory. Don't commit this file.

```bash
cd android
keytool -genkey -v \
  -keystore snowdrift.keystore \
  -alias snowdrift \
  -keyalg RSA \
  -keysize 2048 \
  -validity 10000 \
  -storepass YOUR_STORE_PASSWORD \
  -keypass YOUR_KEY_PASSWORD
```

Then add the passwords to `android/local.properties`:

```properties
STORE_FILE=../snowdrift.keystore
STORE_PASSWORD=YOUR_STORE_PASSWORD
KEY_ALIAS=snowdrift
KEY_PASSWORD=YOUR_KEY_PASSWORD
```

### 3. Build

```bash
# Debug build (no keystore needed)
cd android && ./gradlew assembleDebug

# Release build (requires keystore)
cd android && ./gradlew assembleRelease
```

Output APKs land in `android/app/build/outputs/apk/`.

### 4. Install

```bash
adb install android/app/build/outputs/apk/debug/app-debug.apk
# or for release:
adb install android/app/build/outputs/apk/release/app-release.apk
```

## On-device architecture

SnowDrift runs Python on-device via [Chaquopy](https://chaquo.com/). When the app launches:

1. `SnowDriftApp` → starts `PythonDaemonManager`
2. `PythonDaemonManager` → boots Chaquopy Python runtime, launches `daemon_launcher.py`
3. `daemon_launcher.py` → starts:
   - **Main server** (`server.py`) on port 8001 — the agent's brain
   - **Memory sidecar** (`pythonserver.py`) on port 8765 — sovereign memory with Merkle proofs
4. `MainActivity` → talks to the Python backend via HTTP
5. `SnowDriftAccessibilityService` → full phone control (tap, swipe, read screen)
6. `SnowDriftService` → background polling, keeps the agent alive

### Skill dispatch

All skills are registered in `skills/__init__.py` → `SKILL_REGISTRY`. The agent's routing engine selects skills by metadata (description, category, needs_config) — never by hardcoded keyword matching.

### What about `emergentintegrations/`?

It's a stub. On-device, all inference goes through **Ollama** (local or cloud). The stub exists so `from emergentintegrations.llm.chat import LlmChat` doesn't crash — if hit, it returns a clear error telling the user to switch to Ollama.

### What about `backend/.skillname/` directories?

These are runtime state folders. Each skill writes learned data (watchlists, exercise logs, memory branches) to its dot-directory under `backend/`. They're `.gitkeep`'d in the repo because Git doesn't track empty folders, and their contents are gitignored (user-specific data). Don't delete them — the agent expects them at runtime.

## Tech stack

| Layer | Tech |
|---|---|
| Android UI | Kotlin, ViewBinding, Material Design |
| Python runtime | Chaquopy 15.0.1, Python 3.10 |
| Agent server | FastAPI 0.110.3 + Uvicorn |
| Memory | Sovereign Memory (Blake3 + Merkle tree, pure Python) |
| LLM | Ollama (configurable: local or cloud) |
| Accessibility | Android AccessibilityService (full phone control) |
| License | MIT |

## Troubleshooting

**Build fails on Chaquopy / Python wheel compilation:**
- Make sure Python 3.10 (not 3.11+) is installed and `buildPython` in `local.properties` points to it
- On Windows: use forward slashes or escaped backslashes in the path (`C\\:/Users/...`)

**Build fails on keystore:**
- Debug builds don't need one. Use `assembleDebug` to skip signing
- For release builds, generate a keystore (see step 2 above)

**App crashes on launch:**
- Check `adb logcat -s PythonDaemon` for Python startup errors
- Ensure Ollama is running if you're using local inference
- The app expects ports 8001 (agent) and 8765 (memory) to be available on-device

**"emergentintegrations" import error:**
- Shouldn't happen — the stub package is bundled. If it does, check that `emergentintegrations/` is in the Chaquopy source path.