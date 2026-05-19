"""
daemon_launcher.py - Frozen daemon entry point for SnowDrift on-device.

Called by PythonDaemonManager.kt via Chaquopy on every boot.
Runs both FastAPI servers IN-PROCESS (no subprocess) since Chaquopy
does not expose a command-line Python interpreter.
"""
import os
import sys
import threading
import logging
import asyncio
import time

logging.basicConfig(level=logging.WARNING, format='[daemon] %(message)s')
log = logging.getLogger(__name__)

# ── Defaults (Kotlin overrides these via set_env before launch()) ──────────
_DEFAULTS = {
    'SOVEREIGN_STORE_DIR': '/data/data/com.snowdrift/files/sovereign_memory',
    'APP_FILES_DIR':       '/data/data/com.snowdrift/files',
    'DOTENV_PATH':         '/data/data/com.snowdrift/files/.env',
    # MongoDB — point MONGO_URL at Atlas in .env for cloud persistence.
    # Defaults keep the import alive; motor connects lazily (no crash at startup).
    'MONGO_URL':       'mongodb://localhost:27017',
    'DB_NAME':         'snowdrift_local',
    # Ollama — set OLLAMA_BASE_URL + OLLAMA_API_KEY from the Settings screen
    'OLLAMA_BASE_URL': 'http://localhost:11434',
    'OLLAMA_API_KEY':  'ollama',
    'EMERGENT_LLM_KEY': '',
}
for k, v in _DEFAULTS.items():
    os.environ.setdefault(k, v)

_servers = []
_threads = []


def set_env(key: str, value: str):
    """Called from Kotlin to push Android storage paths into os.environ.
    (PyObject lacks a Kotlin __setitem__ bridge — use this helper instead.)"""
    os.environ[str(key)] = str(value)
    # Also re-resolve dotenv path if storage dir changes
    if key == 'APP_FILES_DIR':
        os.environ.setdefault('DOTENV_PATH', os.path.join(str(value), '.env'))
    return True


def _ensure_storage():
    for k in ('SOVEREIGN_STORE_DIR', 'APP_FILES_DIR'):
        try:
            os.makedirs(os.environ[k], exist_ok=True)
        except Exception as e:
            log.warning(f"mkdir {k} failed: {e}")


def _run_server(module_name: str, port: int):
    """Run uvicorn in-process on a dedicated thread with its own event loop.
    Auto-restarts on unhandled crash with exponential backoff."""
    import importlib
    import uvicorn

    backoff = 1
    while True:
        try:
            log.info(f"Starting {module_name} on :{port}")
            # Fresh event loop for this thread
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            module = importlib.import_module(module_name)
            app = getattr(module, 'app')
            config = uvicorn.Config(
                app=app,
                host='127.0.0.1',
                port=port,
                log_level='warning',
                access_log=False,       # saves battery/CPU
                loop='asyncio',
                lifespan='on',
            )
            server = uvicorn.Server(config)
            _servers.append(server)
            loop.run_until_complete(server.serve())
            log.warning(f"{module_name} exited cleanly — restarting")
            backoff = 1
        except Exception as e:
            log.exception(f"{module_name} crashed: {e}")
            time.sleep(min(backoff, 30))
            backoff = min(backoff * 2, 30)
        finally:
            try:
                loop.close()
            except Exception:
                pass


def launch():
    """Start both servers on background threads. Returns immediately."""
    _ensure_storage()

    # Preload the Python path so importlib finds our bundled modules
    script_dir = os.path.dirname(os.path.abspath(__file__))
    if script_dir not in sys.path:
        sys.path.insert(0, script_dir)

    t1 = threading.Thread(target=_run_server, args=('server', 8001),       daemon=True, name='snowdrift-fastapi')
    t2 = threading.Thread(target=_run_server, args=('pythonserver', 8765), daemon=True, name='snowdrift-pyserver')
    t1.start()
    t2.start()
    _threads.extend([t1, t2])
    log.info("Both servers launched — daemon running")
    return True


def stop():
    """Called by Kotlin when the foreground service is being destroyed."""
    for s in _servers:
        try:
            s.should_exit = True
        except Exception:
            pass
    log.info("Daemon stop requested")


def is_running() -> bool:
    return any(t.is_alive() for t in _threads)


if __name__ == '__main__':
    # Local dev: run synchronously so the process stays alive
    launch()
    while is_running():
        time.sleep(60)
