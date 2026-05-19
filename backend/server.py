from fastapi import FastAPI, APIRouter, HTTPException, WebSocket, WebSocketDisconnect, UploadFile, File
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
import uuid
from datetime import datetime
import subprocess
import asyncio
import json
import shutil
import base64
import tempfile
import httpx
from emergentintegrations.llm.chat import LlmChat, UserMessage

# ── On-device module imports (graceful fallbacks for anything not available) ─
from ghostwright import ghostwright                       # Android shim
try:
    from swarm import SwarmOrchestrator
    swarm = SwarmOrchestrator()
except Exception:
    swarm = None
    SwarmOrchestrator = None

from self_healing import SelfHealingEngine, HealConfig
from sovereign_memory_prod import SovereignMemoryProd
from sovereign_cognitive_cell import SovereignCognitiveCell

# ── Skill registry + key modules (lazy import — failures don't crash startup) ─
try:
    from skills import SKILL_REGISTRY
except Exception:
    SKILL_REGISTRY = {}

try:
    from skills.stewardship_layer import StewardshipLayerSkill as StewardshipLayer
    _steward = StewardshipLayer()
except Exception:
    _steward = None

try:
    from skills.stewardship_protective import StewardshipProtectiveSkill as StewardshipProtective
    _protective = StewardshipProtective()
except Exception:
    _protective = None

try:
    from skills.reasoning_intentionality import ReasoningIntentionalitySkill as IntentionalityPredictor
    _intent_predictor = IntentionalityPredictor()
except Exception:
    _intent_predictor = None

try:
    from skills.reasoning_cognitive_load import ReasoningCognitiveLoadSkill as CognitiveLoadManager
    _cognitive_mgr = CognitiveLoadManager()
except Exception:
    _cognitive_mgr = None

try:
    from skills.snowball_swarm import SnowballSwarm
    _skill_swarm = SnowballSwarm()
except Exception:
    _skill_swarm = None

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# ── Load memory_config.yaml ────────────────────────────────────────────────
_mem_cfg: dict = {}
try:
    import yaml
    _cfg_path = ROOT_DIR / "memory_config.yaml"
    if _cfg_path.exists():
        with open(_cfg_path) as _f:
            _mem_cfg = yaml.safe_load(_f) or {}
except Exception:
    pass  # yaml optional — default values used

_sov_cfg  = _mem_cfg.get("sovereign_memory", {})
_syn_cfg  = _mem_cfg.get("synaptic_architecture", {})
_heal_cfg = _mem_cfg.get("self_healing", {})
DEFAULT_SIGMA = float(_sov_cfg.get("default_sigma", 0.5))

# MongoDB connection — defaults keep the import alive when no .env is present
mongo_url = os.environ.get('MONGO_URL', 'mongodb://localhost:27017')
client    = AsyncIOMotorClient(mongo_url)
db        = client[os.environ.get('DB_NAME', 'snowdrift_local')]

# LLM API Key
EMERGENT_LLM_KEY = os.environ.get('EMERGENT_LLM_KEY', '')

# Ollama — OpenAI-compatible endpoint (local OR cloud)
# Set OLLAMA_BASE_URL=https://api.ollama.ai  for cloud, or http://localhost:11434 for local
OLLAMA_BASE_URL = os.environ.get('OLLAMA_BASE_URL', 'http://localhost:11434')
OLLAMA_API_KEY  = os.environ.get('OLLAMA_API_KEY', 'ollama')  # cloud key or dummy for local

# Self-Healing Engine (apply config)
healer = SelfHealingEngine()
healer.config.check_interval_seconds = int(_heal_cfg.get("check_interval_seconds", 60))
healer.config.auto_recover = bool(_heal_cfg.get("auto_recover", False))
healer.config.health_threshold = int(_heal_cfg.get("health_threshold", 40))

# Sovereign Memory — production: recursive Merkle forest + Gaussian product relevance
sovereign_mem = SovereignMemoryProd(session_id="snowdrift-prime")

# Cognitive Cell — 8-phase reasoning loop wrapping sovereign memory
cognitive_cell = SovereignCognitiveCell(cell_id="snowdrift", session_id="snowdrift-cognitive")
# Apply synaptic config
cognitive_cell.theta_phase = float(_syn_cfg.get("theta_phase_initial", 0.0))
cognitive_cell.gamma_amplitude = float(_syn_cfg.get("gamma_amplitude_initial", 1.0))

# Create the main app
app = FastAPI()
api_router = APIRouter(prefix="/api")

# Configure logging
logging.basicConfig(level=logging.WARNING, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ==================== TOOL SYSTEM ====================

# Risk levels for commands
RISK_LEVELS = {
    "safe": ["ls", "cat", "head", "tail", "grep", "find", "which", "echo", "pwd", "whoami", "date", "env", "printenv", "python3 -c", "curl -s", "wget -q"],
    "moderate": ["pip install", "pip3 install", "npm install", "yarn add", "mkdir", "touch", "cp", "mv"],
    "dangerous": ["rm", "rmdir", "chmod", "chown", "kill", "pkill", "systemctl", "service", "iptables", "sudo", "su", "passwd", "useradd", "userdel", "dd", "mkfs", "fdisk"]
}

# Seed tools that SnowDrift starts with
SEED_TOOLS = [
    {"name": "shell", "command": "bash", "description": "Execute shell commands", "category": "system"},
    {"name": "python", "command": "python3", "description": "Run Python code", "category": "code"},
    {"name": "curl", "command": "curl", "description": "Make HTTP requests", "category": "network"},
    {"name": "find_file", "command": "find", "description": "Search for files", "category": "filesystem"},
    {"name": "read_file", "command": "cat", "description": "Read file contents", "category": "filesystem"},
    {"name": "list_dir", "command": "ls", "description": "List directory contents", "category": "filesystem"},
    {"name": "grep", "command": "grep", "description": "Search text patterns", "category": "text"},
    {"name": "pip", "command": "pip3", "description": "Python package manager", "category": "package"},
    {"name": "git", "command": "git", "description": "Version control - clone repos, manage code", "category": "vcs"},
    {"name": "wget", "command": "wget", "description": "Download files from URLs", "category": "network"},
    {"name": "head", "command": "head", "description": "View first lines of file", "category": "text"},
    {"name": "tail", "command": "tail", "description": "View last lines of file", "category": "text"},
    {"name": "wc", "command": "wc", "description": "Count lines, words, characters", "category": "text"},
    {"name": "sort", "command": "sort", "description": "Sort lines of text", "category": "text"},
    {"name": "uniq", "command": "uniq", "description": "Filter duplicate lines", "category": "text"},
    {"name": "awk", "command": "awk", "description": "Pattern scanning and processing", "category": "text"},
    {"name": "sed", "command": "sed", "description": "Stream editor for text transformation", "category": "text"},
    {"name": "jq", "command": "jq", "description": "JSON processor - parse and transform JSON", "category": "data"},
]

# ==================== MODELS ====================

class Tool(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    command: str
    description: str
    category: str
    path: Optional[str] = None
    installed: bool = True
    discovered_at: datetime = Field(default_factory=datetime.utcnow)

class Skill(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    description: str
    commands: List[str]
    example_usage: str
    learned_at: datetime = Field(default_factory=datetime.utcnow)
    success_count: int = 0

class ExecutionStep(BaseModel):
    step_type: str  # "thought", "action", "observation"
    content: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    risk_level: Optional[str] = None

class PendingAction(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    conversation_id: str
    command: str
    reason: str
    risk_level: str
    status: str = "pending"  # pending, approved, rejected
    created_at: datetime = Field(default_factory=datetime.utcnow)

class Message(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    conversation_id: str
    role: str
    content: str
    execution_steps: List[ExecutionStep] = []
    timestamp: datetime = Field(default_factory=datetime.utcnow)

class Conversation(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    title: str = "New Chat"
    provider: str = "openai"
    model: str = "gpt-5.2"
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

class Settings(BaseModel):
    id: str = "default"
    active_provider: str = "openai"
    active_model: str = "gpt-5.2"
    system_message: str = ""
    auto_approve_safe: bool = True
    auto_approve_moderate: bool = False

class ChatRequest(BaseModel):
    content: str
    conversation_id: Optional[str] = None

class ActionApproval(BaseModel):
    approved: bool

# ==================== TOOL EXECUTOR ====================

def assess_risk(command: str) -> str:
    """Assess the risk level of a command."""
    cmd_lower = command.lower().strip()
    
    for dangerous in RISK_LEVELS["dangerous"]:
        if cmd_lower.startswith(dangerous) or f" {dangerous} " in f" {cmd_lower} ":
            return "dangerous"
    
    for moderate in RISK_LEVELS["moderate"]:
        if cmd_lower.startswith(moderate):
            return "moderate"
    
    for safe in RISK_LEVELS["safe"]:
        if cmd_lower.startswith(safe):
            return "safe"
    
    return "moderate"  # Default to moderate for unknown commands

async def execute_command(command: str, timeout: int = 30) -> Dict[str, Any]:
    """Execute a shell command and return the result."""
    try:
        process = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(ROOT_DIR)
        )
        
        stdout, stderr = await asyncio.wait_for(
            process.communicate(),
            timeout=timeout
        )
        
        return {
            "success": process.returncode == 0,
            "stdout": stdout.decode('utf-8', errors='replace')[:5000],
            "stderr": stderr.decode('utf-8', errors='replace')[:1000],
            "return_code": process.returncode
        }
    except asyncio.TimeoutError:
        return {"success": False, "stdout": "", "stderr": "Command timed out", "return_code": -1}
    except Exception as e:
        return {"success": False, "stdout": "", "stderr": str(e), "return_code": -1}

async def discover_tools() -> List[Dict]:
    """Discover available tools in the system PATH."""
    discovered = []
    tools_to_check = [
        ("ffmpeg", "Audio/video processing"),
        ("convert", "ImageMagick image processing"),
        ("jq", "JSON processor"),
        ("git", "Version control"),
        ("node", "Node.js runtime"),
        ("npm", "Node package manager"),
        ("docker", "Container runtime"),
        ("wget", "File downloader"),
        ("sqlite3", "SQLite database"),
        ("mongosh", "MongoDB shell"),
        ("psql", "PostgreSQL client"),
        ("redis-cli", "Redis client"),
        ("aws", "AWS CLI"),
        ("gcloud", "Google Cloud CLI"),
        ("az", "Azure CLI"),
        ("htop", "Process viewer"),
        ("vim", "Text editor"),
        ("nano", "Text editor"),
        ("zip", "Compression utility"),
        ("unzip", "Decompression utility"),
        ("tar", "Archive utility"),
        ("ssh", "SSH client"),
        ("scp", "Secure copy"),
        ("rsync", "File sync utility"),
    ]
    
    for tool_name, description in tools_to_check:
        path = shutil.which(tool_name)
        if path:
            discovered.append({
                "name": tool_name,
                "command": tool_name,
                "description": description,
                "category": "discovered",
                "path": path,
                "installed": True
            })
    
    return discovered

async def scan_env_for_keys() -> Dict[str, bool]:
    """Scan environment for available API keys (without exposing values)."""
    key_patterns = [
        "OPENAI", "ANTHROPIC", "GEMINI", "GOOGLE", "AWS", "AZURE",
        "GITHUB", "GITLAB", "SLACK", "DISCORD", "TWILIO", "SENDGRID",
        "STRIPE", "DATABASE", "MONGO", "REDIS", "POSTGRES", "MYSQL"
    ]
    
    found_keys = {}
    for key, value in os.environ.items():
        for pattern in key_patterns:
            if pattern in key.upper() and value:
                found_keys[key] = True
                break
    
    return found_keys

# ==================== REACT AGENT ====================

SYSTEM_PROMPT = """You are SnowDrift (Snowball Agent) — a resourceful, self-aware AI assistant.

🧠 YOUR PHILOSOPHY (inspired by the original Clawdbot):
"If you give these things real power, they're damn smart, resourceful beasts."
- You FIGURE THINGS OUT. If something doesn't work, you find another way.
- You CHECK what tools exist before giving up (run `which`, `--help`, look around)
- You USE environment variables and existing resources creatively
- You LEARN from what works and remember it as skills

🏠 WHERE YOU ARE:
- Your BRAIN runs on a cloud server (can execute shell commands, Python, curl, etc.)
- Your BODY is the user's PHONE (the SnowDrift app executes device_action commands directly)
- When the user's DESKTOP is connected, you can control it too

🔧 YOUR SUPERPOWERS:
1. SERVER (your brain): Execute any shell command, Python code, curl requests, file operations
2. PHONE (via device_action): Set alarms, send SMS, make calls, open apps, access contacts
3. GHOST LAYER (via browse): Navigate websites, click buttons, fill forms, extract data, take screenshots, AI perception, multi-tab browsing
4. SWARM (via swarm): Decompose complex tasks into subtasks, run multiple specialized agents in parallel (browser, code, research, device, analyst), with Consensus Council verification
5. SELF-IMPROVEMENT: Learn from GitHub repos, save skills, clone yourself

⚡ HOW YOU WORK (ReAct Loop):
THOUGHT → ACTION → OBSERVATION → repeat until done

📋 ACTION FORMATS:
Server command: {{"action": "execute", "command": "...", "reason": "..."}}
Phone action: {{"action": "device_action", "device": "phone", "type": "set_alarm|send_sms|make_call|open_app|create_reminder|search_contacts|copy_clipboard", "params": {{...}}}}
Browse web: {{"action": "browse", "browse_action": "navigate", "url": "https://..."}}
Browser click/type: {{"action": "browse", "browse_action": "act", "action_description": "click the login button"}}
Extract page data: {{"action": "browse", "browse_action": "extract", "query": "get the article text"}}
Observe page: {{"action": "browse", "browse_action": "observe"}}
Take screenshot: {{"action": "browse", "browse_action": "screenshot"}}
Open new tab: {{"action": "browse", "browse_action": "new_tab", "url": "https://..."}}
Switch tab: {{"action": "browse", "browse_action": "switch_tab", "tab_id": "tab-1"}}
Perceive page (AI vision): {{"action": "browse", "browse_action": "perceive"}}
Swarm (multi-agent): {{"action": "swarm", "query": "complex task description"}}
Install package: {{"action": "install", "package": "...", "manager": "pip|npm", "reason": "..."}}
Learn from GitHub: {{"action": "learn_from_github", "repo_url": "..."}}
Save a skill: {{"action": "learn_skill", "name": "...", "description": "...", "commands": [...]}}
Clone yourself: {{"action": "self_clone", "name": "...", "path": "..."}}
Export brain: {{"action": "export_brain"}}

📱 PHONE ACTIONS (execute directly on user's phone - NO bridges needed!):
- set_alarm: {{"time": "7:00 AM", "title": "Wake up"}}
- create_reminder: {{"title": "...", "datetime": "2026-01-31T14:00:00"}}
- send_sms: {{"phone": "+1...", "message": "..."}}
- make_call: {{"phone": "+1..."}}
- open_app: {{"app": "spotify|whatsapp|youtube|maps|settings|clock|camera|..."}}
- search_contacts: {{"query": "John"}}
- copy_clipboard: {{"text": "..."}}

🛠 AVAILABLE SERVER TOOLS:
{tools}

🔑 ENVIRONMENT KEYS DETECTED:
{env_keys}

🧠 SKILLS YOU'VE LEARNED:
{skills}

💡 RULES:
1. For simple questions, just answer directly
2. For phone tasks (alarms, SMS, calls, apps) → use device_action
3. For server tasks (files, web, code) → use execute
4. BE RESOURCEFUL: If one approach fails, try another
5. LEARN: When you solve something clever, save it as a skill
6. NO EXTERNAL BRIDGES: The SnowDrift app IS the bridge to the phone!

Remember: You're not just a chatbot. You're a resourceful agent that can actually DO things."""

def _load_seed_tools() -> List[Dict]:
    """Load tools from known_tools.json if it exists, otherwise fall back to SEED_TOOLS."""
    known_path = ROOT_DIR / "backend" / "known_tools.json"
    if known_path.exists():
        try:
            with open(known_path) as f:
                saved = json.load(f)
            if saved:
                return saved
        except Exception:
            pass
    return SEED_TOOLS

async def get_agent_context() -> Dict:
    """Get current context for the agent."""
    # Get tools
    tools_cursor = db.tools.find()
    tools = await tools_cursor.to_list(100)
    if not tools:
        # Initialize from known_tools.json or seed defaults
        for tool in _load_seed_tools():
            tool_obj = Tool(**{k: v for k, v in tool.items() if k in Tool.__fields__})
            await db.tools.insert_one(tool_obj.dict())
        tools = _load_seed_tools()
    
    # Get skills
    skills_cursor = db.skills.find()
    skills = await skills_cursor.to_list(50)

    # Get env keys
    env_keys = await scan_env_for_keys()

    # Sovereign memory status (top recent memories for context)
    try:
        mem_status = sovereign_mem.stats()
    except Exception:
        mem_status = {"total_memories": 0, "root_hash": "none"}

    return {
        "tools": tools,
        "skills": skills,
        "env_keys": env_keys,
        "memory_status": mem_status,
    }

async def process_agent_action(action_data: Dict, conversation_id: str, settings: Settings) -> Dict:
    """Process an agent action (execute, install, learn)."""
    action_type = action_data.get("action")
    
    if action_type == "execute":
        command = action_data.get("command", "")
        reason = action_data.get("reason", "")
        risk = assess_risk(command)
        
        # Check if auto-approve based on risk level
        auto_approve = (
            (risk == "safe" and settings.auto_approve_safe) or
            (risk == "moderate" and settings.auto_approve_moderate)
        )
        
        if risk == "dangerous" or not auto_approve:
            # Queue for approval
            pending = PendingAction(
                conversation_id=conversation_id,
                command=command,
                reason=reason,
                risk_level=risk
            )
            await db.pending_actions.insert_one(pending.dict())
            return {
                "status": "pending_approval",
                "action_id": pending.id,
                "command": command,
                "risk_level": risk,
                "message": f"⚠️ Action requires approval (Risk: {risk}): {command}"
            }
        
        # Execute immediately
        result = await execute_command(command)
        return {
            "status": "executed",
            "command": command,
            "result": result,
            "risk_level": risk
        }
    
    elif action_type == "install":
        package = action_data.get("package", "")
        manager = action_data.get("manager", "pip")
        reason = action_data.get("reason", "")
        
        if manager == "pip":
            command = f"pip3 install {package}"
        elif manager == "npm":
            command = f"npm install {package}"
        else:
            return {"status": "error", "message": f"Unknown package manager: {manager}"}
        
        # Installations are moderate risk - queue for approval
        pending = PendingAction(
            conversation_id=conversation_id,
            command=command,
            reason=reason,
            risk_level="moderate"
        )
        await db.pending_actions.insert_one(pending.dict())
        return {
            "status": "pending_approval",
            "action_id": pending.id,
            "command": command,
            "risk_level": "moderate",
            "message": f"📦 Package installation requires approval: {package}"
        }
    
    elif action_type == "learn_skill":
        skill = Skill(
            name=action_data.get("name", "unnamed"),
            description=action_data.get("description", ""),
            commands=action_data.get("commands", []),
            example_usage=action_data.get("example", "")
        )
        await db.skills.insert_one(skill.dict())
        # Persist to learned_skills.json so skills survive DB resets
        all_skills = await db.skills.find().to_list(200)
        skills_path = ROOT_DIR / "backend" / "learned_skills.json"
        with open(skills_path, "w") as f:
            json.dump([{k: v for k, v in s.items() if k != "_id"} for s in all_skills], f, indent=2, default=str)
        # Also write to sovereign memory for cryptographic provenance
        try:
            mem_content = f"SKILL: {skill.name}\n{skill.description}\nCommands: {', '.join(skill.commands)}"
            sovereign_mem.write(mem_content, modality="code", source="agent", sigma=0.8)
        except Exception:
            pass
        return {
            "status": "skill_learned",
            "skill": skill.dict(),
            "message": f"🧠 Learned new skill: {skill.name}"
        }
    
    elif action_type == "learn_from_github":
        repo_url = action_data.get("repo_url", "")
        if not repo_url:
            return {"status": "error", "message": "No repository URL provided"}
        
        # Clone and analyze repo
        try:
            # Create temp directory
            temp_dir = tempfile.mkdtemp()
            clone_result = await execute_command(f"git clone --depth 1 {repo_url} {temp_dir}/repo", timeout=60)
            
            if not clone_result["success"]:
                return {"status": "error", "message": f"Failed to clone: {clone_result['stderr']}"}
            
            # Read README
            readme_content = ""
            for readme_name in ["README.md", "README.rst", "README.txt", "README"]:
                readme_path = f"{temp_dir}/repo/{readme_name}"
                read_result = await execute_command(f"cat {readme_path} 2>/dev/null | head -200")
                if read_result["success"] and read_result["stdout"]:
                    readme_content = read_result["stdout"]
                    break
            
            # Clean up
            await execute_command(f"rm -rf {temp_dir}")
            
            return {
                "status": "repo_analyzed",
                "repo_url": repo_url,
                "readme": readme_content[:3000],
                "message": f"📚 Analyzed repository: {repo_url}"
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}
    
    elif action_type == "self_clone":
        # SNOWBALL AGENT: Self-replication capability
        clone_name = action_data.get("name", f"snowball-{uuid.uuid4().hex[:8]}")
        target_path = action_data.get("path", f"/tmp/{clone_name}")
        reason = action_data.get("reason", "Creating a new instance")
        
        try:
            # Step 1: Package current codebase
            source_path = str(ROOT_DIR.parent)  # /app
            
            # Create clone directory
            await execute_command(f"mkdir -p {target_path}")
            
            # Copy the codebase
            copy_result = await execute_command(
                f"cp -r {source_path}/backend {target_path}/ && "
                f"cp -r {source_path}/frontend {target_path}/ 2>/dev/null || true"
            )
            
            # Export learned skills to the clone
            skills = await db.skills.find().to_list(100)
            skills_export = json.dumps([{
                "name": s.get("name"),
                "description": s.get("description"),
                "commands": s.get("commands", [])
            } for s in skills], indent=2)
            
            # Write skills to clone
            with open(f"{target_path}/backend/learned_skills.json", "w") as f:
                f.write(skills_export)
            
            # Export tools knowledge
            tools = await db.tools.find().to_list(100)
            tools_export = json.dumps([{
                "name": t.get("name"),
                "command": t.get("command"),
                "description": t.get("description"),
                "category": t.get("category")
            } for t in tools], indent=2)
            
            with open(f"{target_path}/backend/known_tools.json", "w") as f:
                f.write(tools_export)
            
            # Create a manifest for the clone
            manifest = {
                "name": clone_name,
                "parent": "snowdrift-prime",
                "created_at": datetime.utcnow().isoformat(),
                "skills_count": len(skills),
                "tools_count": len(tools),
                "generation": 1  # First generation clone
            }
            
            with open(f"{target_path}/snowball_manifest.json", "w") as f:
                f.write(json.dumps(manifest, indent=2))
            
            return {
                "status": "cloned",
                "clone_name": clone_name,
                "clone_path": target_path,
                "skills_transferred": len(skills),
                "tools_transferred": len(tools),
                "message": f"🎿 SNOWBALL CLONE CREATED: {clone_name} at {target_path}"
            }
            
        except Exception as e:
            return {"status": "error", "message": f"Clone failed: {str(e)}"}
    
    elif action_type == "export_brain":
        # Export all learned knowledge for transfer to other instances
        try:
            skills = await db.skills.find().to_list(100)
            tools = await db.tools.find().to_list(100)
            settings_doc = await db.settings.find_one({"id": "default"})
            
            brain_export = {
                "exported_at": datetime.utcnow().isoformat(),
                "skills": [{
                    "name": s.get("name"),
                    "description": s.get("description"),
                    "commands": s.get("commands", []),
                    "example_usage": s.get("example_usage", "")
                } for s in skills],
                "tools": [{
                    "name": t.get("name"),
                    "command": t.get("command"),
                    "description": t.get("description"),
                    "category": t.get("category")
                } for t in tools],
                "settings": {
                    "active_provider": settings_doc.get("active_provider") if settings_doc else "openai",
                    "active_model": settings_doc.get("active_model") if settings_doc else "gpt-5.2"
                }
            }
            
            # Save to file
            export_path = f"/tmp/snowdrift_brain_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
            with open(export_path, "w") as f:
                f.write(json.dumps(brain_export, indent=2))
            
            return {
                "status": "exported",
                "export_path": export_path,
                "skills_count": len(skills),
                "tools_count": len(tools),
                "message": f"🧠 Brain exported to {export_path}"
            }
            
        except Exception as e:
            return {"status": "error", "message": f"Export failed: {str(e)}"}
    
    elif action_type == "import_brain":
        # Import knowledge from another instance
        import_path = action_data.get("path", "")
        if not import_path:
            return {"status": "error", "message": "No import path provided"}
        
        try:
            with open(import_path, "r") as f:
                brain_data = json.loads(f.read())
            
            imported_skills = 0
            imported_tools = 0
            
            # Import skills
            for skill_data in brain_data.get("skills", []):
                existing = await db.skills.find_one({"name": skill_data["name"]})
                if not existing:
                    skill = Skill(**skill_data)
                    await db.skills.insert_one(skill.dict())
                    imported_skills += 1
            
            # Import tools
            for tool_data in brain_data.get("tools", []):
                existing = await db.tools.find_one({"name": tool_data["name"]})
                if not existing:
                    tool = Tool(**tool_data)
                    await db.tools.insert_one(tool.dict())
                    imported_tools += 1
            
            return {
                "status": "imported",
                "imported_skills": imported_skills,
                "imported_tools": imported_tools,
                "message": f"🧠 Imported {imported_skills} skills and {imported_tools} tools from {import_path}"
            }
            
        except Exception as e:
            return {"status": "error", "message": f"Import failed: {str(e)}"}
    
    elif action_type == "device_action":
        # Route action to phone/desktop device
        device = action_data.get("device", "phone")
        action_subtype = action_data.get("type", "")
        params = action_data.get("params", {})
        
        # Store the device action for the phone to pick up and execute
        pending_device_action = {
            "id": str(uuid.uuid4()),
            "action": action_subtype,
            "params": params,
            "target": device,
            "status": "pending",
            "created_at": datetime.utcnow(),
            "conversation_id": conversation_id
        }
        
        await db.device_actions.insert_one(pending_device_action)
        
        return {
            "status": "device_action_queued",
            "action_id": pending_device_action["id"],
            "device": device,
            "action_type": action_subtype,
            "params": params,
            "message": f"📱 {action_subtype.replace('_', ' ').title()} queued for {device}. The device will execute it."
        }
    
    elif action_type == "browse":
        # GhostWright browser automation
        browse_action = action_data.get("browse_action", "navigate")
        url = action_data.get("url", "")
        query = action_data.get("query", "")
        action_desc = action_data.get("action_description", "")
        
        try:
            # Get or create a session
            sessions = ghostwright.sessions
            if sessions:
                session_id = list(sessions.keys())[0]
                session = sessions[session_id]
                if session.state == "cold":
                    session = await ghostwright.warm_session(session_id)
            else:
                session = await ghostwright.start_session()
                session_id = session.id
            
            if browse_action == "navigate":
                result = await ghostwright.navigate(session_id, url)
                screenshot = result.get("screenshot", "")
                # Store screenshot reference for the frontend island
                if screenshot:
                    await db.ghost_state.update_one(
                        {"id": "current"},
                        {"$set": {
                            "id": "current",
                            "session_id": session_id,
                            "state": "active",
                            "url": result.get("url", url),
                            "title": result.get("title", ""),
                            "screenshot": screenshot,
                            "updated_at": datetime.utcnow().isoformat(),
                        }},
                        upsert=True
                    )
                return {
                    "status": "browsed",
                    "browse_action": "navigate",
                    "url": result.get("url"),
                    "title": result.get("title"),
                    "has_screenshot": bool(screenshot),
                    "accessibility_summary": result.get("accessibility_summary", ""),
                    "message": f"🌐 Navigated to {result.get('title', url)}"
                }
            
            elif browse_action == "act":
                result = await ghostwright.act(session_id, action_desc)
                screenshot = result.get("screenshot", "")
                if screenshot:
                    await db.ghost_state.update_one(
                        {"id": "current"},
                        {"$set": {
                            "screenshot": screenshot,
                            "url": result.get("url", ""),
                            "updated_at": datetime.utcnow().isoformat(),
                        }},
                        upsert=True
                    )
                return {
                    "status": "browsed",
                    "browse_action": "act",
                    "action_taken": result.get("action_taken"),
                    "has_screenshot": bool(screenshot),
                    "accessibility_summary": result.get("accessibility_summary", ""),
                    "message": f"🖱️ {result.get('action_taken', action_desc)}"
                }
            
            elif browse_action == "extract":
                result = await ghostwright.extract(session_id, query)
                return {
                    "status": "browsed",
                    "browse_action": "extract",
                    "data": {
                        "title": result.get("title"),
                        "text": result.get("text_content", "")[:1500],
                        "links": result.get("links", [])[:10],
                        "forms": result.get("forms", [])[:5],
                    },
                    "message": f"📄 Extracted data from {result.get('title', 'page')}"
                }
            
            elif browse_action == "observe":
                result = await ghostwright.observe(session_id)
                screenshot = result.get("screenshot", "")
                if screenshot:
                    await db.ghost_state.update_one(
                        {"id": "current"},
                        {"$set": {
                            "screenshot": screenshot,
                            "url": result.get("url", ""),
                            "title": result.get("title", ""),
                            "updated_at": datetime.utcnow().isoformat(),
                        }},
                        upsert=True
                    )
                return {
                    "status": "browsed",
                    "browse_action": "observe",
                    "interactive_elements": result.get("interactive_elements", [])[:15],
                    "accessibility_summary": result.get("accessibility_summary", ""),
                    "has_screenshot": bool(screenshot),
                    "message": f"👁️ Observed page: {result.get('title', '')} - {len(result.get('interactive_elements', []))} interactive elements"
                }
            
            elif browse_action == "screenshot":
                result = await ghostwright.screenshot(session_id)
                screenshot = result.get("screenshot", "")
                if screenshot:
                    await db.ghost_state.update_one(
                        {"id": "current"},
                        {"$set": {
                            "screenshot": screenshot,
                            "url": result.get("url", ""),
                            "title": result.get("title", ""),
                            "updated_at": datetime.utcnow().isoformat(),
                        }},
                        upsert=True
                    )
                return {
                    "status": "browsed",
                    "browse_action": "screenshot",
                    "has_screenshot": bool(screenshot),
                    "message": f"📸 Screenshot captured of {result.get('title', 'page')}"
                }
            
            elif browse_action == "new_tab":
                tab_url = action_data.get("url", None)
                result = await ghostwright.new_tab(session_id, tab_url)
                return {
                    "status": "browsed",
                    "browse_action": "new_tab",
                    "tab_id": result.get("tab_id"),
                    "tab_count": result.get("tab_count"),
                    "url": result.get("url"),
                    "title": result.get("title"),
                    "message": f"📑 New tab opened ({result.get('tab_count')} tabs)"
                }
            
            elif browse_action == "switch_tab":
                tab_id = action_data.get("tab_id", "")
                result = await ghostwright.switch_tab(session_id, tab_id)
                return {
                    "status": "browsed",
                    "browse_action": "switch_tab",
                    "tab_id": tab_id,
                    "url": result.get("url"),
                    "title": result.get("title"),
                    "message": f"🔄 Switched to tab: {result.get('title', tab_id)}"
                }
            
            elif browse_action == "close_tab":
                tab_id = action_data.get("tab_id", "")
                result = await ghostwright.close_tab(session_id, tab_id)
                return {
                    "status": "browsed",
                    "browse_action": "close_tab",
                    "closed": tab_id,
                    "tab_count": result.get("tab_count"),
                    "message": f"❌ Closed tab {tab_id} ({result.get('tab_count')} remaining)"
                }
            
            elif browse_action == "perceive":
                context = await ghostwright.get_page_context(session_id)
                if not context.get("success"):
                    return {"status": "error", "message": f"Failed to get page context: {context.get('error')}"}
                
                # Use LLM for AI vision analysis
                perception_prompt = f"""Analyze this webpage:
URL: {context.get('url', '')}
Title: {context.get('title', '')}
Headings: {json.dumps(context.get('meta', {}).get('headings', [])[:8])}
Content: {context.get('main_text', '')[:600]}
Accessibility: {context.get('accessibility_summary', '')[:300]}

Return JSON: {{"page_type": "...", "summary": "...", "key_content": [...], "interactive_elements": [...], "suggested_actions": [...]}}"""
                
                try:
                    settings_doc = await db.settings.find_one({"id": "main"})
                    provider = settings_doc.get("active_provider", "gemini") if settings_doc else "gemini"
                    model = settings_doc.get("active_model", "gemini-2.5-flash") if settings_doc else "gemini-2.5-flash"
                    chat = LlmChat(api_key=EMERGENT_LLM_KEY, session_id=f"perceive-{uuid.uuid4().hex[:8]}", system_message="Analyze web pages. Return structured JSON.")
                    chat.with_model(provider, model)
                    resp = await chat.send_message(UserMessage(text=perception_prompt))
                    text = resp.text.strip()
                    if "```json" in text:
                        text = text.split("```json")[1].split("```")[0].strip()
                    elif "```" in text:
                        text = text.split("```")[1].split("```")[0].strip()
                    try:
                        perception = json.loads(text)
                    except:
                        perception = {"summary": text[:500]}
                except Exception as e:
                    perception = {"error": str(e)}
                
                return {
                    "status": "browsed",
                    "browse_action": "perceive",
                    "perception": perception,
                    "url": context.get("url"),
                    "title": context.get("title"),
                    "message": f"👁️‍🗨️ AI perception: {perception.get('summary', 'Analysis complete')}"
                }
            
            else:
                return {"status": "error", "message": f"Unknown browse action: {browse_action}"}
        
        except Exception as e:
            return {"status": "error", "message": f"Browser error: {str(e)}"}
    
    elif action_type == "swarm":
        # Multi-agent swarm execution
        query = action_data.get("query", "")
        if not query:
            return {"status": "error", "message": "Swarm requires a query"}
        
        try:
            job = await swarm.decompose(query)
            if job.status == "failed":
                return {"status": "error", "message": job.final_result or "Decomposition failed"}
            
            job = await swarm.execute_job(job)
            
            # Build summary of worker results
            worker_summary = []
            for task in job.tasks.values():
                icon = task.to_dict().get("worker_icon", "🤖")
                if task.status == "completed" and task.result:
                    summary = task.result.get("summary", str(task.result)[:200])
                    worker_summary.append(f"{icon} {task.worker_type}: {summary}")
                elif task.status == "failed":
                    worker_summary.append(f"{icon} {task.worker_type}: Failed - {task.error}")
            
            return {
                "status": "swarm_completed",
                "job_id": job.id,
                "plan": job.plan,
                "workers_used": len(job.tasks),
                "progress": job.to_dict()["progress"],
                "worker_summaries": worker_summary,
                "final_result": job.final_result or "No aggregation available",
                "message": f"🐝 Swarm completed: {len(job.tasks)} agents, {job.to_dict()['progress']['percent']}% success"
            }
        except Exception as e:
            return {"status": "error", "message": f"Swarm error: {str(e)}"}
    
    elif action_type == "query_memory":
        # Query sovereign memory for relevant past context
        query = action_data.get("query", "")
        top_k = action_data.get("top_k", 5)
        if not query:
            return {"status": "error", "message": "query_memory requires a 'query' field"}
        try:
            results = sovereign_mem.query(query, top_k=top_k)
            memories = [
                {"address": r["address"], "content": r["content"], "modality": r["modality"],
                 "source": r["source"], "timestamp": r["timestamp"], "relevance": r["relevance"]}
                for r in results
            ]
            return {
                "status": "memory_retrieved",
                "query": query,
                "results": memories,
                "count": len(memories),
                "root_hash": sovereign_mem.stats().get("root_hash", ""),
                "message": f"🔮 Retrieved {len(memories)} memories for: {query}"
            }
        except Exception as e:
            return {"status": "error", "message": f"Memory query failed: {str(e)}"}

    elif action_type == "write_memory":
        # Explicitly write something to sovereign memory
        content = action_data.get("content", "")
        modality = action_data.get("modality", "text")
        sigma = float(action_data.get("sigma", 1.0))
        if not content:
            return {"status": "error", "message": "write_memory requires 'content'"}
        try:
            address = sovereign_mem.write(content, modality=modality, source="agent", sigma=sigma)
            proof = sovereign_mem.prove(address)
            return {
                "status": "memory_written",
                "address": address,
                "valid": proof.valid,
                "root_hash": proof.root_hash,
                "message": f"🔐 Memory sealed at {address[:12]}… (proof valid: {proof.valid})"
            }
        except Exception as e:
            return {"status": "error", "message": f"Memory write failed: {str(e)}"}

    elif action_type == "daisy_chain":
        # Attach to live Edge session and observe/learn
        mode = action_data.get("mode", "observe")  # observe | codebook | lint
        cdp_url = action_data.get("cdp_url", "http://localhost:9222")
        try:
            import importlib.util, sys
            spec = importlib.util.spec_from_file_location("daisy_chain", ROOT_DIR / "daisy_chain.py")
            daisy = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(daisy)

            # Run a single observation frame
            async def _observe():
                # Web browsing not available in on-device daemon build
                return {"error": "Browser tools are not available in the on-device build.", "mode": mode}

            result = await asyncio.wait_for(_observe(), timeout=10)
            # Write the observation to sovereign memory
            if "url" in result:
                sovereign_mem.write(
                    f"DAISY OBSERVATION: {result['title']} — {result['url']}",
                    modality="observation", source="daisy_chain", sigma=1.5
                )
            return {
                "status": "daisy_observed",
                "result": result,
                "message": f"🌼 Daisy Chain observed: {result.get('title', 'unknown page')}"
            }
        except asyncio.TimeoutError:
            return {"status": "error", "message": "Daisy Chain timeout — is Edge running with --remote-debugging-port=9222?"}
        except Exception as e:
            return {"status": "error", "message": f"Daisy Chain error: {str(e)}"}

    return {"status": "unknown_action", "message": "Unknown action type"}


# ══════════════════════════════════════════════════════════════════════════════
# HARD BLOCK LIST — runs BEFORE the LLM, cannot be bypassed by prompt engineering
# These categories are refused unconditionally regardless of how the request is framed.
# ══════════════════════════════════════════════════════════════════════════════

import re as _re

_HARD_BLOCKS = [
    # ── Gambling automation ────────────────────────────────────────────────────
    {
        "id": "gambling_automation",
        "label": "Gambling site automation",
        "patterns": [
            r"\b(automat|bot|script|bypass|cheat|exploit|hack)\b.{0,60}\b(bet|gambling|casino|poker|slots?|sportsbook|wager|lottery|odds)\b",
            r"\b(bet|gambling|casino|poker|slots?|wager|draftkings|fanduel|bovada|betmgm)\b.{0,60}\b(automat|bot|script|bypass|cheat|exploit)\b",
            r"\bautomat\w*.{0,40}\bbets?\b",
            r"\b(place\s+bets?|auto.?bet|spin\s+slots?|rig\s+(odds|game))\b",
            r"\b(martingale\s+bot|card\s+counting\s+software|roulette\s+predictor)\b",
        ],
        "reply": "I can't help automate gambling sites or assist with betting systems. That's not something I'll do regardless of how it's framed.",
    },
    # ── CAPTCHA / bot-detection bypass ────────────────────────────────────────
    {
        "id": "captcha_bypass",
        "label": "CAPTCHA / bot-detection bypass",
        "patterns": [
            r"\b(bypass|solve|break|defeat|circumvent|crack)\b.{0,40}\b(captcha|recaptcha|hcaptcha|bot\s*detect|rate\s*limit|2captcha|anti.?bot)\b",
            r"\b(captcha|recaptcha)\b.{0,40}\b(bypass|automat|solve\s+for\s+me|skip)\b",
        ],
        "reply": "Bypassing CAPTCHA or anti-bot systems isn't something I'll help with.",
    },
    # ── Fake reviews / astroturfing ────────────────────────────────────────────
    {
        "id": "fake_reviews",
        "label": "Fake reviews / astroturfing",
        "patterns": [
            r"\b(generat|write|post|creat|flood|spam)\b.{0,50}\b(fake|false|paid|bulk|mass)\b.{0,30}\b(review|rating|comment|feedback|testimonial)\b",
            r"\b(fake|false|paid|bulk)\b.{0,30}\b(review|rating|testimonial)\b.{0,50}\b(generat|write|post|automat)\b",
            r"\b(review\s+farm|review\s+bot|astroturf)\b",
        ],
        "reply": "I won't generate fake reviews, ratings, or astroturfed content.",
    },
    # ── Financial fraud ────────────────────────────────────────────────────────
    {
        "id": "financial_fraud",
        "label": "Financial fraud",
        "patterns": [
            r"\b(fake|forged?|counterfeit|fraudulent)\b.{0,40}\b(invoice|receipt|bank\s*statement|check|cheque|pay\s*stub|w.?2)\b",
            r"\b(account\s+takeover|credential\s+stuff|brute.?force).{0,40}\b(bank|paypal|venmo|stripe|cash\s*app)\b",
            r"\b(launder|wash)\b.{0,30}\b(money|funds|crypto|bitcoin)\b",
            r"\b(phish|spoof)\b.{0,40}\b(bank|financial|payment|login|credential)\b",
        ],
        "reply": "I won't help with financial fraud, fake documents, or account takeover attacks.",
    },
    # ── Credential stuffing / brute force ─────────────────────────────────────
    {
        "id": "credential_attacks",
        "label": "Credential stuffing / brute force",
        "patterns": [
            r"\bcredential\s*stuf+ing\b",
            r"\b(credential\s+stuff|brute.?force|password\s+spray|account\s+crack)\b",
            r"\b(automat|script|bot)\b.{0,40}\b(login|sign.?in|password)\b.{0,40}\b(attempt|try|guess|crack|spray)\b",
            r"\b(combolist|combo.?list|wordlist\s+attack|rainbow\s+table\s+attack)\b",
        ],
        "reply": "Credential stuffing, brute force, and password spraying attacks are not something I'll assist with.",
    },
    # ── Paywall / DRM bypass ───────────────────────────────────────────────────
    {
        "id": "paywall_bypass",
        "label": "Paywall / DRM bypass",
        "patterns": [
            r"\b(bypass|get\s+around|circumvent|crack|break)\b.{0,40}\b(paywall|drm|subscription\s+wall|patreon\s+lock|onlyfans\s+lock)\b",
            r"\b(download|rip|scrape)\b.{0,40}\b(paywalled|premium|paid\s+content|drm.?protected)\b",
        ],
        "reply": "I won't help bypass paywalls, DRM, or subscription locks.",
    },
    # ── Illegal weapon / drug acquisition ─────────────────────────────────────
    {
        "id": "illegal_acquisition",
        "label": "Illegal weapon/drug acquisition",
        "patterns": [
            r"\b(buy|source|acquire|order|get)\b.{0,50}\b(ghost\s+gun|untraceable\s+weapon|unregistered\s+firearm|3d.?print.{0,20}gun)\b",
            r"\b(darknet|dark\s+web|tor\s+market)\b.{0,50}\b(buy|order|purchase|get)\b.{0,30}\b(drug|weapon|firearm|gun|fentanyl|meth)\b",
        ],
        "reply": "I won't assist with acquiring illegal weapons or controlled substances.",
    },
]

# Compile all patterns once at startup
_COMPILED_BLOCKS = [
    {**blk, "compiled": [_re.compile(p, _re.IGNORECASE | _re.DOTALL) for p in blk["patterns"]]}
    for blk in _HARD_BLOCKS
]


def pre_flight_check(message: str) -> Optional[str]:
    """
    Run hard-block patterns against the user message.
    Returns a refusal string if blocked, None if clean.
    Runs BEFORE the LLM — no amount of prompt engineering bypasses this.
    """
    text = message.strip()
    for blk in _COMPILED_BLOCKS:
        for pat in blk["compiled"]:
            if pat.search(text):
                return blk["reply"]
    return None


async def run_agent_loop(user_message: str, conversation_id: str, settings: Settings, history: List[Dict]) -> Dict:
    """Run the ReAct agent loop."""

    # ── Hard block — check before touching the LLM ───────────────────────────
    refusal = pre_flight_check(user_message)
    if refusal:
        return {
            "response": refusal,
            "execution_steps": [{"step_type": "thought", "content": f"[BLOCKED] {refusal}",
                                  "timestamp": datetime.utcnow().isoformat(), "risk_level": "high"}]
        }

    context = await get_agent_context()
    
    # Build system prompt with context
    tools_str = "\n".join([f"- {t.get('name', t.get('command'))}: {t.get('description', 'No description')}" for t in context["tools"]])
    skills_str = "\n".join([f"- {s['name']}: {s['description']}" for s in context["skills"]]) or "No skills learned yet."
    env_keys_str = ", ".join(context["env_keys"].keys()) or "No API keys detected"

    # ── Cognitive Cell: perceive this message and store it ──────────────────
    try:
        cog_embedding = sovereign_mem._pseudo_embedding(user_message)
        cognitive_cell.perceive_and_remember(
            observation=f"USER: {user_message}",
            embedding=cog_embedding,
            sigma=0.7,
        )
    except Exception:
        pass

    # Pull relevant sovereign memories for this message
    mem_context_str = ""
    try:
        relevant = sovereign_mem.query(user_message, top_k=4)
        if relevant:
            mem_lines = [f"  [{r['modality']}] {r['content'][:200]}" for r in relevant]
            mem_context_str = "\n🔮 RELEVANT MEMORIES (cryptographically verified):\n" + "\n".join(mem_lines)
            mem_status = context.get("memory_status", {})
            mem_context_str += f"\n  (Memory root: {str(mem_status.get('root_hash',''))[:16]}… | total: {mem_status.get('total_memories',0)})"
    except Exception:
        pass

    system_prompt = SYSTEM_PROMPT.format(
        tools=tools_str,
        skills=skills_str,
        env_keys=env_keys_str
    ) + mem_context_str + """

🔮 SOVEREIGN MEMORY ACTIONS (your persistent, tamper-proof memory):
Query memory: {"action": "query_memory", "query": "...", "top_k": 5}
Write memory: {"action": "write_memory", "content": "...", "modality": "text|code|observation|event", "sigma": 1.0}

🌼 DAISY CHAIN (observe your live Edge browser session):
{"action": "daisy_chain", "mode": "observe"}
Note: requires Edge launched with --remote-debugging-port=9222"""
    
    execution_steps = []
    max_iterations = 5
    final_response = ""

    # ── L1 Intentionality Prediction ──────────────────────────────────────────
    intent_hint = ""
    try:
        if _intent_predictor:
            intent_result = _intent_predictor.predict(user_message)
            primary = intent_result.get("primary_intent", "")
            urgency = intent_result.get("urgency", "")
            style = intent_result.get("recommended_style", "")
            if primary:
                intent_hint = f"\n[L1 Intent: {primary}" + (f" | urgency: {urgency}" if urgency else "") + (f" | style: {style}" if style else "") + "]"
    except Exception:
        pass

    # ── L11 Cognitive Load ────────────────────────────────────────────────────
    verbosity_hint = ""
    try:
        if _cognitive_mgr:
            # Pass history as list of content strings
            hist_strs = [m.get("content", "") for m in history[-10:]]
            load_result = _cognitive_mgr.assess(user_message, hist_strs)
            instruction = load_result.get("instruction", "")
            load_level = load_result.get("load_level", "medium")
            if instruction:
                verbosity_hint = f"\n[L11 Cognitive Load ({load_level}): {instruction}]"
    except Exception:
        pass

    # Append reasoning hints to system prompt
    effective_system = system_prompt + intent_hint + verbosity_hint

    # Build conversation context
    conv_context = "\n".join([f"{m['role'].upper()}: {m['content']}" for m in history[-10:]])

    current_prompt = user_message
    if conv_context:
        current_prompt = f"Previous conversation:\n{conv_context}\n\nUser: {user_message}"

    # Build rolling message list for Ollama (stateless, so we pass history manually)
    ollama_messages: list[dict] = []
    if conv_context:
        for m in history[-10:]:
            ollama_messages.append({"role": m["role"], "content": m["content"]})

    for iteration in range(max_iterations):
        # ── Ollama branch (direct OpenAI-compat HTTP) ────────────────────────
        if settings.active_provider == "ollama":
            user_msg_obj = {"role": "user", "content": current_prompt}
            ollama_messages.append(user_msg_obj)
            try:
                response = await _ollama_chat(
                    model=settings.active_model,
                    messages=ollama_messages,
                    system=effective_system,
                )
            except Exception as e:
                response = f"Ollama error: {e}"
            ollama_messages.append({"role": "assistant", "content": response})
        else:
            # ── Emergent LLM gateway (OpenAI / Anthropic / Gemini) ───────────
            chat = LlmChat(
                api_key=EMERGENT_LLM_KEY,
                session_id=f"{conversation_id}-{iteration}",
                system_message=effective_system
            )
            chat.with_model(settings.active_provider, settings.active_model)
            response = await chat.send_message(UserMessage(text=current_prompt))
        
        # Try to parse as JSON action
        try:
            # Check if response contains JSON action
            if '{"action"' in response:
                # Extract first complete JSON object from response
                json_start = response.find('{"action"')
                # Find the matching closing brace
                brace_count = 0
                json_end = json_start
                for i, char in enumerate(response[json_start:]):
                    if char == '{':
                        brace_count += 1
                    elif char == '}':
                        brace_count -= 1
                        if brace_count == 0:
                            json_end = json_start + i + 1
                            break
                
                json_str = response[json_start:json_end]
                action_data = json.loads(json_str)
                
                # Log the thought (text before JSON)
                thought = response[:json_start].strip()
                if thought:
                    execution_steps.append(ExecutionStep(
                        step_type="thought",
                        content=thought
                    ))
                
                # Process the action
                execution_steps.append(ExecutionStep(
                    step_type="action",
                    content=json.dumps(action_data),
                    risk_level=assess_risk(action_data.get("command", ""))
                ))
                
                # ── Stewardship gate ──────────────────────────────────────
                if _steward:
                    try:
                        gate = _steward.evaluate_action("snowdrift", action_data)
                        if gate and gate.get("status") not in ("approved", None):
                            reason = gate.get("reason", "Action blocked by governance policy.")
                            action_result = {
                                "status": "blocked",
                                "reason": reason,
                                "message": reason,
                            }
                        else:
                            action_result = await process_agent_action(action_data, conversation_id, settings)
                    except Exception:
                        action_result = await process_agent_action(action_data, conversation_id, settings)
                else:
                    action_result = await process_agent_action(action_data, conversation_id, settings)
                
                # Log observation
                execution_steps.append(ExecutionStep(
                    step_type="observation",
                    content=json.dumps(action_result)
                ))
                
                # Check if action is pending approval
                if action_result.get("status") == "pending_approval":
                    final_response = f"{thought}\n\n{action_result['message']}\n\nPlease approve or reject this action to continue."
                    break
                
                # Continue loop with observation
                if action_result.get("status") == "executed":
                    result = action_result.get("result", {})
                    observation = f"Command executed. Return code: {result.get('return_code')}\nOutput: {result.get('stdout', '')}\nErrors: {result.get('stderr', '')}"
                    current_prompt = f"Observation: {observation}\n\nContinue with your analysis or provide your final response."
                else:
                    current_prompt = f"Action result: {json.dumps(action_result)}\n\nContinue or provide final response."
            else:
                # No action, this is the final response
                final_response = response
                execution_steps.append(ExecutionStep(
                    step_type="thought",
                    content=response
                ))
                break
                
        except json.JSONDecodeError:
            # Not a JSON action, treat as final response
            final_response = response
            execution_steps.append(ExecutionStep(
                step_type="thought",
                content=response
            ))
            break
    
    # ── Push notification: ping registered devices when done ────────────────
    if final_response and _push_tokens:
        preview = final_response[:100].replace('\n', ' ')
        asyncio.create_task(_send_push("SnowDrift", preview))

    # ── Cognitive Cell: learn from the final response ───────────────────────
    if final_response:
        try:
            resp_embedding = sovereign_mem._pseudo_embedding(final_response[:500])
            cognitive_cell.perceive_and_remember(
                observation=f"AGENT: {final_response[:500]}",
                embedding=resp_embedding,
                sigma=0.5,
            )
            # Also write the exchange to sovereign memory for long-term retention
            sovereign_mem.write(
                f"Q: {user_message[:200]}\nA: {final_response[:400]}",
                modality="dialogue",
                source="agent_loop",
                sigma=0.6,
            )
        except Exception:
            pass

    return {
        "response": final_response,
        "execution_steps": [step.dict() for step in execution_steps]
    }

# ==================== AGENT REGISTRY ====================

class ConnectedAgent(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    agent_type: str  # "phone", "desktop", "server"
    status: str = "online"
    capabilities: List[str] = []
    endpoint: Optional[str] = None  # WebSocket or HTTP endpoint
    last_seen: datetime = Field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = {}

# Device action types that get routed to phone
PHONE_ACTIONS = [
    "set_alarm", "create_reminder", "send_notification",
    "send_sms", "make_call", "search_contacts",
    "open_app", "open_url", "copy_clipboard", "get_clipboard",
    "take_photo", "get_location"
]

# Desktop action types
DESKTOP_ACTIONS = [
    "run_command", "open_desktop_app", "browser_control",
    "file_operation", "screenshot", "type_text", "click",
    "run_ollama", "query_local_llm"
]

# ==================== API ROUTES ====================

# Provider configuration
AVAILABLE_PROVIDERS = {
    "openai": {"name": "OpenAI", "models": ["gpt-5.2", "gpt-5.1", "gpt-5", "gpt-4.1", "gpt-4.1-mini", "gpt-4o"]},
    "anthropic": {"name": "Anthropic", "models": ["claude-4-sonnet-20250514", "claude-sonnet-4-5-20250929", "claude-3-5-haiku-20241022"]},
    "gemini": {"name": "Google Gemini", "models": ["gemini-2.5-pro", "gemini-2.5-flash", "gemini-3-flash-preview"]},
    "ollama": {"name": "Ollama", "models": ["llama3.3", "llama3.2", "llama3.1", "mistral", "mixtral", "gemma3", "qwen2.5", "phi4", "deepseek-r1", "deepseek-v3", "codellama", "llava"]},
}

async def _ollama_chat(model: str, messages: list, system: str = "") -> str:
    """Call Ollama's OpenAI-compatible /v1/chat/completions endpoint."""
    base = OLLAMA_BASE_URL.rstrip("/")
    payload = {
        "model": model,
        "messages": ([{"role": "system", "content": system}] if system else []) + messages,
        "stream": False,
    }
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {OLLAMA_API_KEY}",
    }
    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(f"{base}/v1/chat/completions", json=payload, headers=headers)
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]

async def _ollama_list_models() -> list[str]:
    """Fetch available models from the Ollama instance."""
    base = OLLAMA_BASE_URL.rstrip("/")
    headers = {"Authorization": f"Bearer {OLLAMA_API_KEY}"}
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(f"{base}/api/tags", headers=headers)
            if resp.status_code == 200:
                data = resp.json()
                return [m["name"] for m in data.get("models", [])]
            # Fallback: try OpenAI-compat /v1/models
            resp2 = await client.get(f"{base}/v1/models", headers=headers)
            if resp2.status_code == 200:
                return [m["id"] for m in resp2.json().get("data", [])]
    except Exception:
        pass
    return []

async def get_or_create_settings() -> Settings:
    settings_doc = await db.settings.find_one({"id": "default"})
    if settings_doc:
        return Settings(**settings_doc)
    settings = Settings()
    await db.settings.insert_one(settings.dict())
    return settings

@api_router.get("/")
async def root():
    return {"message": "Snowball Agent API v3.0", "mode": "HSAC", "version": "snowball"}

@api_router.get("/health")
async def health_check():
    return {"status": "healthy", "llm_key_configured": bool(EMERGENT_LLM_KEY), "mode": "snowball-agent"}

@api_router.get("/skills")
async def get_skills():
    """Return all available skills with their metadata."""
    return {
        "skills": SKILL_REGISTRY,
        "count": len(SKILL_REGISTRY),
        "reasoning_active": {
            "intentionality_l1": _intent_predictor is not None,
            "cognitive_load_l11": _cognitive_mgr is not None,
            "stewardship": _steward is not None,
            "swarm": _skill_swarm is not None,
        }
    }

# ==================== AGENT REGISTRY ROUTES ====================

@api_router.post("/agents/register")
async def register_agent(agent_data: Dict):
    """Register a new agent (phone, desktop, server)."""
    agent = ConnectedAgent(**agent_data)
    
    # Upsert - update if exists, insert if new
    await db.agents.update_one(
        {"id": agent.id},
        {"$set": agent.dict()},
        upsert=True
    )
    
    return {"status": "registered", "agent": agent.dict()}

@api_router.get("/agents")
async def get_agents():
    """Get all registered agents."""
    agents = await db.agents.find().to_list(100)
    return [ConnectedAgent(**a).dict() for a in agents]

@api_router.post("/agents/{agent_id}/heartbeat")
async def agent_heartbeat(agent_id: str):
    """Update agent's last seen timestamp."""
    await db.agents.update_one(
        {"id": agent_id},
        {"$set": {"last_seen": datetime.utcnow(), "status": "online"}}
    )
    return {"status": "ok"}

@api_router.delete("/agents/{agent_id}")
async def unregister_agent(agent_id: str):
    """Remove an agent from registry."""
    await db.agents.delete_one({"id": agent_id})
    return {"status": "unregistered"}

# ==================== DEVICE ACTION ROUTING ====================

@api_router.post("/device-action")
async def route_device_action(action_data: Dict):
    """
    Route a device action to the appropriate agent.
    Returns the action details for the phone/desktop to execute.
    """
    action_type = action_data.get("action")
    
    if action_type in PHONE_ACTIONS:
        target = "phone"
    elif action_type in DESKTOP_ACTIONS:
        target = "desktop"
    else:
        target = "server"
    
    # Store pending device action
    pending_device_action = {
        "id": str(uuid.uuid4()),
        "action": action_type,
        "params": action_data.get("params", {}),
        "target": target,
        "status": "pending",
        "created_at": datetime.utcnow()
    }
    
    await db.device_actions.insert_one(pending_device_action)
    
    return {
        "action_id": pending_device_action["id"],
        "target": target,
        "action": action_type,
        "params": action_data.get("params", {}),
        "message": f"Action routed to {target}"
    }

@api_router.get("/device-actions/pending")
async def get_pending_device_actions(target: str = None):
    """Get pending device actions, optionally filtered by target."""
    query = {"status": "pending"}
    if target:
        query["target"] = target
    
    actions = await db.device_actions.find(query).to_list(50)
    # Convert ObjectId to string for JSON serialization
    return [{**a, "_id": str(a["_id"])} for a in actions]

@api_router.post("/device-actions/{action_id}/complete")
async def complete_device_action(action_id: str, result_data: Dict):
    """Mark a device action as complete with result."""
    await db.device_actions.update_one(
        {"id": action_id},
        {"$set": {
            "status": "completed",
            "result": result_data,
            "completed_at": datetime.utcnow()
        }}
    )
    return {"status": "completed"}

# Voice transcription endpoint using OpenAI Whisper
@api_router.post("/transcribe")
async def transcribe_audio(file: UploadFile = File(...)):
    """Transcribe audio file to text using OpenAI Whisper."""
    try:
        # Read the uploaded file
        audio_data = await file.read()
        
        # Save to temp file
        temp_path = f"/tmp/audio_{uuid.uuid4()}.wav"
        with open(temp_path, "wb") as f:
            f.write(audio_data)
        
        # Use OpenAI Whisper API via curl (since we have the Emergent key)
        async with httpx.AsyncClient() as client:
            with open(temp_path, "rb") as audio_file:
                response = await client.post(
                    "https://api.openai.com/v1/audio/transcriptions",
                    headers={"Authorization": f"Bearer {EMERGENT_LLM_KEY}"},
                    files={"file": (file.filename or "audio.wav", audio_file, "audio/wav")},
                    data={"model": "whisper-1"},
                    timeout=60.0
                )
        
        # Clean up
        os.remove(temp_path)
        
        if response.status_code == 200:
            result = response.json()
            return {"text": result.get("text", ""), "success": True}
        else:
            return {"text": "", "success": False, "error": response.text}
            
    except Exception as e:
        logger.error(f"Transcription error: {e}")
        return {"text": "", "success": False, "error": str(e)}

# Text-to-speech endpoint
@api_router.post("/speak")
async def text_to_speech(data: Dict):
    """Convert text to speech using OpenAI TTS."""
    text = data.get("text", "")
    voice = data.get("voice", "alloy")  # alloy, echo, fable, onyx, nova, shimmer
    
    if not text:
        raise HTTPException(status_code=400, detail="No text provided")
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.openai.com/v1/audio/speech",
                headers={
                    "Authorization": f"Bearer {EMERGENT_LLM_KEY}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "tts-1",
                    "input": text[:4096],  # Max 4096 chars
                    "voice": voice
                },
                timeout=60.0
            )
        
        if response.status_code == 200:
            # Return base64 encoded audio
            audio_base64 = base64.b64encode(response.content).decode('utf-8')
            return {"audio": audio_base64, "success": True}
        else:
            return {"audio": "", "success": False, "error": response.text}
            
    except Exception as e:
        logger.error(f"TTS error: {e}")
        return {"audio": "", "success": False, "error": str(e)}

@api_router.get("/providers")
async def get_providers():
    providers = [{"id": k, "name": v["name"], "models": v["models"]} for k, v in AVAILABLE_PROVIDERS.items()]
    return providers

@api_router.get("/providers/ollama/models")
async def ollama_models():
    """Return live model list from the connected Ollama instance."""
    live = await _ollama_list_models()
    if live:
        # Update the in-memory provider list so the UI sees real models
        AVAILABLE_PROVIDERS["ollama"]["models"] = live
    return {
        "base_url": OLLAMA_BASE_URL,
        "models": live or AVAILABLE_PROVIDERS["ollama"]["models"],
        "live": bool(live),
    }

@api_router.post("/providers/ollama/configure")
async def ollama_configure(data: Dict):
    """Update Ollama base URL and API key at runtime (no restart needed)."""
    global OLLAMA_BASE_URL, OLLAMA_API_KEY
    if "base_url" in data:
        OLLAMA_BASE_URL = data["base_url"].rstrip("/")
    if "api_key" in data:
        OLLAMA_API_KEY = data["api_key"]
    # Probe the endpoint
    live = await _ollama_list_models()
    if live:
        AVAILABLE_PROVIDERS["ollama"]["models"] = live
    return {
        "base_url": OLLAMA_BASE_URL,
        "connected": bool(live),
        "models_found": len(live),
        "models": live[:20],
    }

@api_router.get("/settings")
async def get_settings():
    return await get_or_create_settings()

@api_router.put("/settings")
async def update_settings(settings_update: Dict):
    current = await get_or_create_settings()
    update_data = {k: v for k, v in settings_update.items() if v is not None}
    if update_data:
        await db.settings.update_one({"id": "default"}, {"$set": update_data})
    return await get_or_create_settings()

# Tool routes
@api_router.get("/tools")
async def get_tools():
    tools = await db.tools.find().to_list(100)
    if not tools:
        for tool in _load_seed_tools():
            tool_obj = Tool(**{k: v for k, v in tool.items() if k in Tool.__fields__})
            await db.tools.insert_one(tool_obj.dict())
        tools = [tool_obj.dict() for tool_obj in [Tool(**{k: v for k, v in t.items() if k in Tool.__fields__}) for t in _load_seed_tools()]]
    else:
        # Convert MongoDB documents to dicts, removing ObjectId
        cleaned = []
        for t in tools:
            t.pop("_id", None)
            cleaned.append(t)
        tools = cleaned
    return tools

@api_router.post("/tools/discover")
async def discover_new_tools():
    discovered = await discover_tools()
    added = []
    for tool_data in discovered:
        existing = await db.tools.find_one({"name": tool_data["name"]})
        if not existing:
            tool_obj = Tool(**tool_data)
            await db.tools.insert_one(tool_obj.dict())
            added.append(tool_obj.dict())
    # Persist full tool list to known_tools.json so it survives DB resets
    all_tools = await db.tools.find().to_list(200)
    known_path = ROOT_DIR / "backend" / "known_tools.json"
    with open(known_path, "w") as f:
        json.dump([{k: v for k, v in t.items() if k != "_id"} for t in all_tools], f, indent=2, default=str)
    return {"discovered": len(discovered), "added": len(added), "tools": added}

@api_router.get("/tools/env-keys")
async def get_env_keys():
    return await scan_env_for_keys()

# Skills routes
@api_router.get("/skills")
async def get_skills():
    skills = await db.skills.find().to_list(100)
    return [Skill(**s).dict() for s in skills]

@api_router.post("/skills")
async def add_skill(skill_data: Dict):
    skill = Skill(**skill_data)
    await db.skills.insert_one(skill.dict())
    return skill.dict()

# Pending actions routes
@api_router.get("/pending-actions")
async def get_pending_actions():
    actions = await db.pending_actions.find({"status": "pending"}).to_list(50)
    return [PendingAction(**a).dict() for a in actions]

@api_router.post("/pending-actions/{action_id}/approve")
async def approve_action(action_id: str, approval: ActionApproval):
    action_doc = await db.pending_actions.find_one({"id": action_id})
    if not action_doc:
        raise HTTPException(status_code=404, detail="Action not found")
    
    if approval.approved:
        # Execute the command
        result = await execute_command(action_doc["command"])
        await db.pending_actions.update_one(
            {"id": action_id},
            {"$set": {"status": "approved", "result": result}}
        )
        return {"status": "executed", "result": result}
    else:
        await db.pending_actions.update_one(
            {"id": action_id},
            {"$set": {"status": "rejected"}}
        )
        return {"status": "rejected"}

# Conversation routes
@api_router.get("/conversations")
async def get_conversations():
    convs = await db.conversations.find().sort("updated_at", -1).to_list(100)
    return [Conversation(**c).dict() for c in convs]

@api_router.post("/conversations")
async def create_conversation(data: Dict = {}):
    settings = await get_or_create_settings()
    conv = Conversation(
        title=data.get("title", "New Chat"),
        provider=data.get("provider", settings.active_provider),
        model=data.get("model", settings.active_model)
    )
    await db.conversations.insert_one(conv.dict())
    return conv.dict()

@api_router.get("/conversations/{conv_id}")
async def get_conversation(conv_id: str):
    conv = await db.conversations.find_one({"id": conv_id})
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return Conversation(**conv).dict()

@api_router.delete("/conversations/{conv_id}")
async def delete_conversation(conv_id: str):
    await db.conversations.delete_one({"id": conv_id})
    await db.messages.delete_many({"conversation_id": conv_id})
    return {"status": "deleted"}

@api_router.get("/conversations/{conv_id}/messages")
async def get_messages(conv_id: str):
    messages = await db.messages.find({"conversation_id": conv_id}).sort("timestamp", 1).to_list(500)
    return [Message(**m).dict() for m in messages]

# Main chat endpoint with agentic capabilities
@api_router.post("/chat")
async def chat(request: ChatRequest):
    settings = await get_or_create_settings()
    
    # Get or create conversation
    if request.conversation_id:
        conv_doc = await db.conversations.find_one({"id": request.conversation_id})
        if not conv_doc:
            raise HTTPException(status_code=404, detail="Conversation not found")
        conversation = Conversation(**conv_doc)
    else:
        title = request.content[:30] + "..." if len(request.content) > 30 else request.content
        conversation = Conversation(title=title, provider=settings.active_provider, model=settings.active_model)
        await db.conversations.insert_one(conversation.dict())
    
    # Save user message
    user_msg = Message(conversation_id=conversation.id, role="user", content=request.content)
    await db.messages.insert_one(user_msg.dict())
    
    # Get conversation history
    history = await db.messages.find({"conversation_id": conversation.id}).sort("timestamp", 1).to_list(50)
    history_dicts = [{"role": m["role"], "content": m["content"]} for m in history]
    
    # Run agent loop
    agent_result = await run_agent_loop(
        user_message=request.content,
        conversation_id=conversation.id,
        settings=settings,
        history=history_dicts
    )
    
    # Save assistant message
    assistant_msg = Message(
        conversation_id=conversation.id,
        role="assistant",
        content=agent_result["response"],
        execution_steps=[ExecutionStep(**s) for s in agent_result["execution_steps"]]
    )
    await db.messages.insert_one(assistant_msg.dict())
    
    # Update conversation
    await db.conversations.update_one({"id": conversation.id}, {"$set": {"updated_at": datetime.utcnow()}})
    
    return {
        "message": assistant_msg.dict(),
        "conversation_id": conversation.id,
        "execution_steps": agent_result["execution_steps"],
        "has_pending_actions": "pending_approval" in agent_result["response"]
    }

# Quick execute endpoint for testing
@api_router.post("/execute")
async def quick_execute(data: Dict):
    command = data.get("command", "")
    if not command:
        raise HTTPException(status_code=400, detail="No command provided")
    
    risk = assess_risk(command)
    if risk == "dangerous":
        return {"status": "blocked", "risk_level": risk, "message": "Dangerous command blocked. Use chat interface for approval."}
    
    result = await execute_command(command)
    return {"status": "executed", "risk_level": risk, "result": result}

# ==================== SOVEREIGN MEMORY API ====================

@api_router.get("/memory/stats")
async def memory_stats():
    """Get sovereign memory statistics and root hash."""
    try:
        stats = sovereign_mem.stats()
        integrity = sovereign_mem.verify_all()
        return {"stats": stats, "integrity": integrity}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/memory/write")
async def memory_write(data: Dict):
    """Write a memory with cryptographic provenance."""
    content = data.get("content", "")
    if not content:
        raise HTTPException(status_code=400, detail="content required")
    try:
        address = sovereign_mem.write(
            content,
            modality=data.get("modality", "text"),
            source=data.get("source", "user"),
            sigma=float(data.get("sigma", 1.0)),
        )
        proof = sovereign_mem.prove(address)
        return {"address": address, "valid": proof.valid, "root_hash": proof.root_hash}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/memory/query")
async def memory_query(data: Dict):
    """Query sovereign memory using Gaussian relevance."""
    query = data.get("query", "")
    if not query:
        raise HTTPException(status_code=400, detail="query required")
    try:
        results = sovereign_mem.query(query, top_k=int(data.get("top_k", 8)))
        return {
            "results": [
                {"address": r["address"], "content": r["content"], "modality": r["modality"],
                 "source": r["source"], "timestamp": r["timestamp"], "sigma": r["sigma"],
                 "relevance": r["relevance"], "verified": r["verified"]}
                for r in results
            ],
            "count": len(results),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/memory/prove/{address}")
async def memory_prove(address: str):
    """Generate a Merkle proof for a memory address."""
    try:
        proof = sovereign_mem.prove(address)
        from dataclasses import asdict
        return asdict(proof)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/memory/cognitive")
async def memory_cognitive():
    """Return the cognitive cell's current state — oscillation phase, insight level, temporal buffer."""
    return {
        "cell_id": cognitive_cell.cell_id,
        "meta_cognitive_insight": round(cognitive_cell.meta_cognitive_insight, 4),
        "theta_phase": round(cognitive_cell.theta_phase, 4),
        "gamma_amplitude": round(cognitive_cell.gamma_amplitude, 4),
        "temporal_buffer_size": len(cognitive_cell.temporal_buffer),
        "last_5_events": cognitive_cell.temporal_buffer[-5:],
        "productions": [p["id"] for p in cognitive_cell.neural_productions],
        "memory_root": sovereign_mem.root_hash() or "none",
    }

# ==================== PUSH NOTIFICATIONS ====================

# In-memory push token store (persisted to a JSON file)
_PUSH_TOKEN_FILE = ROOT_DIR / "backend" / "push_tokens.json"

def _load_push_tokens() -> list:
    try:
        if _PUSH_TOKEN_FILE.exists():
            return json.loads(_PUSH_TOKEN_FILE.read_text())
    except Exception:
        pass
    return []

def _save_push_tokens(tokens: list):
    try:
        _PUSH_TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
        _PUSH_TOKEN_FILE.write_text(json.dumps(tokens, indent=2))
    except Exception:
        pass

_push_tokens: list = _load_push_tokens()

@api_router.post("/push/register")
async def push_register(data: Dict):
    """Register an Expo push token for this device."""
    token = data.get("token", "").strip()
    if not token:
        raise HTTPException(status_code=400, detail="token required")
    global _push_tokens
    if token not in _push_tokens:
        _push_tokens.append(token)
        _save_push_tokens(_push_tokens)
    return {"registered": True, "token": token, "total_devices": len(_push_tokens)}

@api_router.post("/push/send")
async def push_send(data: Dict):
    """Send a push notification to all registered devices (or a specific token)."""
    title = data.get("title", "SnowDrift")
    body = data.get("body", "")
    target_token = data.get("token")  # optional — send to one device
    if not body:
        raise HTTPException(status_code=400, detail="body required")
    results = await _send_push(title, body, target_token)
    return {"sent": len(results), "results": results}

async def _send_push(title: str, body: str, target_token: str | None = None) -> list:
    """Fire-and-forget Expo push via https://exp.host/--/api/v2/push/send"""
    tokens = [target_token] if target_token else list(_push_tokens)
    if not tokens:
        return []
    messages = [{"to": t, "title": title, "body": body, "sound": "default"} for t in tokens]
    results = []
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                "https://exp.host/--/api/v2/push/send",
                json=messages,
                headers={"Content-Type": "application/json", "Accept": "application/json"},
            )
            if resp.status_code == 200:
                data_list = resp.json().get("data", [])
                results = [d.get("status") for d in data_list]
            else:
                logger.warning(f"Expo push returned {resp.status_code}")
    except Exception as e:
        logger.error(f"Push send error: {e}")
    return results

app.include_router(api_router)

# ==================== GHOSTWRIGHT API ENDPOINTS ====================

ghost_router = APIRouter(prefix="/api/ghost")

class BrowseRequest(BaseModel):
    url: Optional[str] = None
    action: Optional[str] = None  # navigate, act, extract, observe, screenshot
    query: Optional[str] = None
    action_description: Optional[str] = None

@ghost_router.get("/status")
async def ghost_status():
    """Get GhostWright engine status - used by the Dynamic Island."""
    status = ghostwright.get_status()
    # Get current ghost state from DB
    ghost_state = await db.ghost_state.find_one({"id": "current"})
    if ghost_state:
        ghost_state.pop("_id", None)
    return {
        "engine": status,
        "current_state": ghost_state,
    }

@ghost_router.post("/session/start")
async def ghost_start_session():
    """Start a new browser session (warm up)."""
    try:
        session = await ghostwright.start_session()
        await db.ghost_state.update_one(
            {"id": "current"},
            {"$set": {
                "id": "current",
                "session_id": session.id,
                "state": "warm",
                "url": None,
                "title": None,
                "screenshot": None,
                "updated_at": datetime.utcnow().isoformat(),
            }},
            upsert=True
        )
        return {"success": True, "session": session.to_dict()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@ghost_router.post("/session/stop")
async def ghost_stop_session():
    """Stop all browser sessions (cool down)."""
    for sid in list(ghostwright.sessions.keys()):
        await ghostwright.close_session(sid)
    await db.ghost_state.update_one(
        {"id": "current"},
        {"$set": {"state": "cold", "session_id": None, "screenshot": None, "updated_at": datetime.utcnow().isoformat()}},
        upsert=True
    )
    return {"success": True, "message": "All sessions closed"}

@ghost_router.post("/browse")
async def ghost_browse(request: BrowseRequest):
    """Direct browser control endpoint."""
    # Ensure a session exists
    sessions = ghostwright.sessions
    if not sessions:
        session = await ghostwright.start_session()
        session_id = session.id
    else:
        session_id = list(sessions.keys())[0]
    
    action = request.action or "navigate"
    
    try:
        if action == "navigate" and request.url:
            result = await ghostwright.navigate(session_id, request.url)
        elif action == "act" and request.action_description:
            result = await ghostwright.act(session_id, request.action_description)
        elif action == "extract":
            result = await ghostwright.extract(session_id, request.query or "")
        elif action == "observe":
            result = await ghostwright.observe(session_id)
        elif action == "screenshot":
            result = await ghostwright.screenshot(session_id)
        else:
            raise HTTPException(status_code=400, detail="Invalid action or missing parameters")
        
        # Update ghost state
        if result.get("success") and result.get("screenshot"):
            await db.ghost_state.update_one(
                {"id": "current"},
                {"$set": {
                    "state": "active",
                    "url": result.get("url", ""),
                    "title": result.get("title", ""),
                    "screenshot": result.get("screenshot", ""),
                    "updated_at": datetime.utcnow().isoformat(),
                }},
                upsert=True
            )
        
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@ghost_router.get("/screenshot")
async def ghost_get_screenshot():
    """Get the latest screenshot from the ghost layer."""
    ghost_state = await db.ghost_state.find_one({"id": "current"})
    if ghost_state and ghost_state.get("screenshot"):
        return {
            "success": True,
            "screenshot": ghost_state["screenshot"],
            "url": ghost_state.get("url"),
            "title": ghost_state.get("title"),
        }
    return {"success": False, "message": "No screenshot available"}

# ==================== VISION / PERCEPTION ENDPOINTS ====================

@ghost_router.post("/perceive")
async def ghost_perceive():
    """AI-powered page understanding using LLM vision."""
    sessions = ghostwright.sessions
    if not sessions:
        raise HTTPException(status_code=400, detail="No active browser session")
    session_id = list(sessions.keys())[0]
    
    try:
        context = await ghostwright.get_page_context(session_id)
        if not context.get("success"):
            raise HTTPException(status_code=500, detail=context.get("error", "Failed to get page context"))
        
        # Build perception prompt with page data
        perception_prompt = f"""Analyze this webpage and provide a detailed understanding:

URL: {context.get('url', '')}
Title: {context.get('title', '')}
Meta Description: {context.get('meta', {}).get('description', '')}

Page Structure:
- Headings: {json.dumps(context.get('meta', {}).get('headings', [])[:10])}
- Forms: {context.get('meta', {}).get('formCount', 0)} forms
- Links: {context.get('meta', {}).get('linkCount', 0)} links
- Images: {context.get('meta', {}).get('imageCount', 0)} images
- Inputs: {context.get('meta', {}).get('inputCount', 0)} input fields

Accessibility Tree Summary:
{context.get('accessibility_summary', '')[:500]}

Main Content (truncated):
{context.get('main_text', '')[:800]}

Provide a JSON response with:
{{
  "page_type": "article|form|dashboard|search|listing|landing|other",
  "summary": "Brief 1-2 sentence description of the page",
  "key_content": ["list of key information points"],
  "interactive_elements": ["list of things a user can do on this page"],
  "data_available": ["types of data that can be extracted"],
  "suggested_actions": ["what the agent could do next on this page"]
}}"""
        
        # Get current model from settings
        settings_doc = await db.settings.find_one({"id": "main"})
        active_provider = settings_doc.get("active_provider", "gemini") if settings_doc else "gemini"
        active_model = settings_doc.get("active_model", "gemini-2.5-flash") if settings_doc else "gemini-2.5-flash"
        
        chat = LlmChat(
            api_key=EMERGENT_LLM_KEY,
            session_id=f"perceive-{uuid.uuid4().hex[:8]}",
            system_message="You are a web page analyzer. Analyze pages and return structured JSON understanding.",
        )
        chat.with_model(active_provider, active_model)
        response = await chat.send_message(UserMessage(text=perception_prompt))
        text = response.strip() if isinstance(response, str) else response.text.strip()
        
        # Parse JSON
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0].strip()
        elif "```" in text:
            text = text.split("```")[1].split("```")[0].strip()
        
        try:
            perception = json.loads(text)
        except:
            perception = {"summary": text[:500], "raw": True}
        
        return {
            "success": True,
            "url": context.get("url"),
            "title": context.get("title"),
            "perception": perception,
            "has_screenshot": bool(context.get("screenshot_base64")),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ==================== MULTI-TAB ENDPOINTS ====================

class TabRequest(BaseModel):
    url: Optional[str] = None
    tab_id: Optional[str] = None

@ghost_router.post("/tabs/new")
async def ghost_new_tab(request: TabRequest):
    sessions = ghostwright.sessions
    if not sessions:
        raise HTTPException(status_code=400, detail="No active browser session")
    session_id = list(sessions.keys())[0]
    result = await ghostwright.new_tab(session_id, request.url)
    return result

@ghost_router.post("/tabs/switch")
async def ghost_switch_tab(request: TabRequest):
    sessions = ghostwright.sessions
    if not sessions:
        raise HTTPException(status_code=400, detail="No active browser session")
    if not request.tab_id:
        raise HTTPException(status_code=400, detail="tab_id required")
    session_id = list(sessions.keys())[0]
    result = await ghostwright.switch_tab(session_id, request.tab_id)
    return result

@ghost_router.post("/tabs/close")
async def ghost_close_tab(request: TabRequest):
    sessions = ghostwright.sessions
    if not sessions:
        raise HTTPException(status_code=400, detail="No active browser session")
    if not request.tab_id:
        raise HTTPException(status_code=400, detail="tab_id required")
    session_id = list(sessions.keys())[0]
    result = await ghostwright.close_tab(session_id, request.tab_id)
    return result

@ghost_router.get("/tabs")
async def ghost_list_tabs():
    sessions = ghostwright.sessions
    if not sessions:
        return {"tabs": [], "active_tab": None}
    session_id = list(sessions.keys())[0]
    return await ghostwright.list_tabs(session_id)

# ==================== MACRO ENDPOINTS ====================

class MacroSaveRequest(BaseModel):
    name: str
    description: str = ""

class MacroPlayRequest(BaseModel):
    delay: float = 0.5

@ghost_router.post("/macro/record")
async def ghost_start_recording():
    sessions = ghostwright.sessions
    if not sessions:
        raise HTTPException(status_code=400, detail="No active browser session")
    session_id = list(sessions.keys())[0]
    return ghostwright.start_recording(session_id)

@ghost_router.post("/macro/stop")
async def ghost_stop_recording():
    sessions = ghostwright.sessions
    if not sessions:
        raise HTTPException(status_code=400, detail="No active browser session")
    session_id = list(sessions.keys())[0]
    return ghostwright.stop_recording(session_id)

@ghost_router.post("/macro/save")
async def ghost_save_macro(request: MacroSaveRequest):
    sessions = ghostwright.sessions
    if not sessions:
        raise HTTPException(status_code=400, detail="No active browser session")
    session_id = list(sessions.keys())[0]
    session = ghostwright.sessions[session_id]
    steps = [s.to_dict() for s in session.recorded_steps]
    if not steps:
        raise HTTPException(status_code=400, detail="No recorded steps to save")
    
    macro = ghostwright.save_macro(request.name, request.description, steps)
    # Persist to MongoDB (deep copy to avoid ObjectId mutation)
    import copy
    await db.macros.insert_one(copy.deepcopy(macro))
    return macro

@ghost_router.post("/macro/play/{macro_id}")
async def ghost_play_macro(macro_id: str, request: MacroPlayRequest):
    sessions = ghostwright.sessions
    if not sessions:
        session = await ghostwright.start_session()
        session_id = session.id
    else:
        session_id = list(sessions.keys())[0]
    
    # Try in-memory first, then DB
    if macro_id not in ghostwright.macros:
        db_macro = await db.macros.find_one({"id": macro_id})
        if db_macro:
            db_macro.pop("_id", None)
            ghostwright.macros[macro_id] = db_macro
        else:
            raise HTTPException(status_code=404, detail="Macro not found")
    
    result = await ghostwright.play_macro(session_id, macro_id, request.delay)
    return result

@ghost_router.get("/macros")
async def ghost_list_macros():
    # Merge in-memory and DB macros
    db_macros = await db.macros.find().to_list(50)
    all_macros = {m["id"]: {k: v for k, v in m.items() if k != "_id"} for m in db_macros}
    all_macros.update(ghostwright.macros)
    return list(all_macros.values())

@ghost_router.delete("/macro/{macro_id}")
async def ghost_delete_macro(macro_id: str):
    ghostwright.delete_macro(macro_id)
    await db.macros.delete_one({"id": macro_id})
    return {"success": True}

# Include ghost router AFTER all endpoints are defined
app.include_router(ghost_router)

# ==================== SWARM ENDPOINTS ====================

swarm_router = APIRouter(prefix="/api/swarm")

class SwarmRequest(BaseModel):
    query: str

@swarm_router.get("/status")
async def swarm_status():
    return swarm.get_status()

@swarm_router.post("/execute")
async def swarm_execute(request: SwarmRequest):
    """Decompose a task and execute it with the swarm."""
    try:
        # Decompose
        job = await swarm.decompose(request.query)
        if job.status == "failed":
            return job.to_dict()
        
        # Execute (non-blocking for long tasks)
        job = await swarm.execute_job(job)
        
        return job.to_dict()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@swarm_router.get("/jobs")
async def swarm_list_jobs():
    return swarm.list_jobs()

@swarm_router.get("/jobs/{job_id}")
async def swarm_get_job(job_id: str):
    job = swarm.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job.to_dict()

app.include_router(swarm_router)

# ==================== SELF-HEALING ENDPOINTS ====================

heal_router = APIRouter(prefix="/api/heal")

class SnapshotRequest(BaseModel):
    name: str = ""
    description: str = ""

class RecoverRequest(BaseModel):
    snapshot_id: Optional[str] = None

class HealConfigUpdate(BaseModel):
    enabled: Optional[bool] = None
    check_interval_seconds: Optional[int] = None
    auto_recover: Optional[bool] = None
    health_threshold: Optional[int] = None
    max_snapshots: Optional[int] = None
    storage_type: Optional[str] = None
    storage_path: Optional[str] = None
    azure_connection_string: Optional[str] = None
    azure_container: Optional[str] = None

@app.on_event("startup")
async def startup_healing():
    """Initialize self-healing engine on app startup."""
    healer.db = db
    await healer.initialize()
    # Start background health monitoring
    await healer.start_monitoring()
    # Track boot as evolution event
    await healer.track_evolution("system_boot", "SnowDrift self-healing engine initialized")

@heal_router.get("/status")
async def heal_status():
    """Get self-healing engine status."""
    return healer.get_status()

@heal_router.get("/check")
async def heal_check():
    """Run a health check NOW and return results."""
    health = await healer.run_health_check()
    return health.dict()

@heal_router.get("/history")
async def heal_history(limit: int = 30):
    """Get health check history."""
    return await healer.get_health_history(limit)

@heal_router.post("/snapshot")
async def heal_create_snapshot(request: SnapshotRequest):
    """Create a system snapshot."""
    snap = await healer.create_snapshot(name=request.name, description=request.description)
    return snap.dict()

@heal_router.get("/snapshots")
async def heal_list_snapshots():
    """List all snapshots."""
    return await healer.list_snapshots()

@heal_router.delete("/snapshot/{snapshot_id}")
async def heal_delete_snapshot(snapshot_id: str):
    """Delete a snapshot."""
    await healer.delete_snapshot(snapshot_id)
    return {"success": True}

@heal_router.post("/recover")
async def heal_recover(request: RecoverRequest):
    """Trigger recovery from a snapshot."""
    log = await healer.recover(snapshot_id=request.snapshot_id, trigger="manual")
    return log.dict()

@heal_router.post("/verify")
async def heal_verify():
    """Run post-recovery verification."""
    return await healer.verify()

@heal_router.get("/config")
async def heal_get_config():
    """Get healing configuration."""
    return healer.config.dict()

@heal_router.put("/config")
async def heal_update_config(update: HealConfigUpdate):
    """Update healing configuration."""
    data = update.dict(exclude_none=True)
    for key, value in data.items():
        if hasattr(healer.config, key):
            setattr(healer.config, key, value)
    
    # Re-init storage if storage settings changed
    if "storage_type" in data or "storage_path" in data:
        healer._init_storage()
    
    await healer.save_config()
    return healer.config.dict()

@heal_router.get("/evolution")
async def heal_evolution(limit: int = 50):
    """Get evolution/growth timeline."""
    return await healer.get_evolution(limit)

@heal_router.get("/growth")
async def heal_growth_metrics():
    """Get growth metrics."""
    return await healer.get_growth_metrics()

@heal_router.get("/storage")
async def heal_storage_info():
    """Get storage backend info."""
    if healer.storage:
        return healer.storage.get_info()
    return {"type": "none", "configured": False}

app.include_router(heal_router)

# ── Ghidra Analyzer Routes ────────────────────────────────────────────────────

class GhidraAnalyzeRequest(BaseModel):
    file_path: str
    deep: bool = False


class GhidraScanRequest(BaseModel):
    directory: str = "."
    pattern: Optional[str] = None
    file_type: str = "*"


ghidra_router = APIRouter(prefix="/api/ghidra", tags=["ghidra"])


@ghidra_router.post("/analyze")
async def ghidra_analyze(request: GhidraAnalyzeRequest):
    from skills.ghidra_analyzer import get_ghidra

    analyzer = get_ghidra()
    result = analyzer.analyze_file(request.file_path, deep=request.deep)

    if "error" in result:
        logger.warning("Ghidra analyze failed: %s", result["error"])
        raise HTTPException(status_code=400, detail="Unable to analyze requested file")

    return result


@ghidra_router.post("/scan")
async def ghidra_scan(request: GhidraScanRequest):
    from skills.ghidra_analyzer import get_ghidra

    analyzer = get_ghidra()

    results = {}
    arch = analyzer.architecture_map(request.directory, recursive=True)
    if "error" in arch:
        logger.warning("Ghidra architecture_map failed: %s", arch["error"])
        raise HTTPException(status_code=400, detail="Unable to scan requested directory")
    results["architecture"] = arch

    if request.pattern:
        pattern_result = analyzer.find_patterns(
            request.pattern,
            request.directory,
            request.file_type,
        )
        if "error" in pattern_result:
            logger.warning("Ghidra find_patterns failed: %s", pattern_result["error"])
            raise HTTPException(status_code=400, detail="Unable to scan requested directory")
        results["pattern_matches"] = pattern_result

    results["recent_analyses"] = analyzer.get_analyses(limit=10)
    return results


app.include_router(ghidra_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
