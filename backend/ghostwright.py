"""
GhostWright Engine v2 - Browser automation + Screen perception + Multi-tab + Macros
Manages headless browser sessions with warm/cold states for battery efficiency.
"""

import asyncio
import base64
import json
import os
import time
import uuid
from datetime import datetime
from typing import Optional, Dict, Any, List
from playwright.async_api import async_playwright, Browser, BrowserContext, Page
from dotenv import load_dotenv

load_dotenv()

CHROME_PATH = '/pw-browsers/chromium-1208/chrome-linux/chrome'


class TabInfo:
    """Represents a single browser tab."""
    def __init__(self, tab_id: str, page: Page):
        self.id = tab_id
        self.page = page
        self.url: Optional[str] = None
        self.title: Optional[str] = None
        self.last_screenshot: Optional[str] = None
        self.accessibility_tree: Optional[Dict] = None

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "url": self.url,
            "title": self.title,
            "has_screenshot": self.last_screenshot is not None,
        }


class MacroStep:
    """A single step in a macro recording."""
    def __init__(self, action: str, params: Dict):
        self.action = action
        self.params = params
        self.timestamp = datetime.utcnow().isoformat()

    def to_dict(self) -> Dict:
        return {"action": self.action, "params": self.params, "timestamp": self.timestamp}


class BrowserSession:
    """Represents a browser session with multi-tab support and macro recording."""

    def __init__(self, session_id: str):
        self.id = session_id
        self.state = "cold"
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.tabs: Dict[str, TabInfo] = {}
        self.active_tab_id: Optional[str] = None
        self.last_activity: float = time.time()
        self.created_at: str = datetime.utcnow().isoformat()
        self.history: List[Dict] = []
        # Macro recording
        self.recording = False
        self.recorded_steps: List[MacroStep] = []

    @property
    def active_tab(self) -> Optional[TabInfo]:
        if self.active_tab_id and self.active_tab_id in self.tabs:
            return self.tabs[self.active_tab_id]
        return None

    @property
    def page(self) -> Optional[Page]:
        tab = self.active_tab
        return tab.page if tab else None

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "state": self.state,
            "current_url": self.active_tab.url if self.active_tab else None,
            "last_activity": self.last_activity,
            "created_at": self.created_at,
            "has_screenshot": (self.active_tab.last_screenshot is not None) if self.active_tab else False,
            "tab_count": len(self.tabs),
            "active_tab_id": self.active_tab_id,
            "tabs": [t.to_dict() for t in self.tabs.values()],
            "recording": self.recording,
            "recorded_steps_count": len(self.recorded_steps),
        }

    def record_step(self, action: str, params: Dict):
        if self.recording:
            self.recorded_steps.append(MacroStep(action, params))


class GhostWrightEngine:
    """
    GhostWright v2 - AI-powered browser automation engine with multi-tab + macros + vision.
    """

    def __init__(self):
        self.sessions: Dict[str, BrowserSession] = {}
        self.playwright = None
        self._playwright_instance = None
        self.max_idle_seconds = 120
        self._cleanup_task = None
        # Saved macros
        self.macros: Dict[str, Dict] = {}

    async def _ensure_playwright(self):
        if not self._playwright_instance:
            os.environ['PLAYWRIGHT_BROWSERS_PATH'] = '/pw-browsers'
            self._playwright_instance = async_playwright()
            self.playwright = await self._playwright_instance.start()
        return self.playwright

    async def start_session(self) -> BrowserSession:
        session_id = str(uuid.uuid4())[:8]
        session = BrowserSession(session_id)
        session.state = "warming"
        self.sessions[session_id] = session

        try:
            pw = await self._ensure_playwright()
            session.browser = await pw.chromium.launch(
                headless=True,
                executable_path=CHROME_PATH,
                args=['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage',
                      '--disable-gpu', '--no-first-run', '--no-zygote', '--single-process',
                      '--disable-extensions']
            )
            session.context = await session.browser.new_context(
                viewport={"width": 1280, "height": 720},
                user_agent="Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 SnowballBot/1.0"
            )
            # Create first tab
            page = await session.context.new_page()
            tab_id = "tab-0"
            tab = TabInfo(tab_id, page)
            session.tabs[tab_id] = tab
            session.active_tab_id = tab_id

            session.state = "warm"
            session.last_activity = time.time()

            if not self._cleanup_task:
                self._cleanup_task = asyncio.create_task(self._auto_cleanup())

            return session
        except Exception as e:
            session.state = "cold"
            raise Exception(f"Failed to start browser session: {str(e)}")

    async def _auto_cleanup(self):
        while True:
            await asyncio.sleep(30)
            now = time.time()
            for sid, session in list(self.sessions.items()):
                if session.state == "warm" and (now - session.last_activity) > self.max_idle_seconds:
                    await self.cool_session(sid)

    async def warm_session(self, session_id: str) -> BrowserSession:
        session = self.sessions.get(session_id)
        if not session:
            return await self.start_session()
        if session.state in ("warm", "active"):
            return session

        session.state = "warming"
        try:
            pw = await self._ensure_playwright()
            session.browser = await pw.chromium.launch(
                headless=True,
                executable_path=CHROME_PATH,
                args=['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage', '--disable-gpu']
            )
            session.context = await session.browser.new_context(viewport={"width": 1280, "height": 720})

            # Re-create tabs
            old_tabs = {tid: t.url for tid, t in session.tabs.items()}
            session.tabs.clear()

            for tid, url in old_tabs.items():
                page = await session.context.new_page()
                tab = TabInfo(tid, page)
                session.tabs[tid] = tab
                if url:
                    try:
                        await page.goto(url, wait_until="domcontentloaded", timeout=15000)
                        tab.url = page.url
                        tab.title = await page.title()
                    except:
                        pass

            if not session.active_tab_id or session.active_tab_id not in session.tabs:
                session.active_tab_id = list(session.tabs.keys())[0] if session.tabs else None

            session.state = "warm"
            session.last_activity = time.time()
            return session
        except Exception as e:
            session.state = "cold"
            raise Exception(f"Failed to warm session: {str(e)}")

    async def cool_session(self, session_id: str):
        session = self.sessions.get(session_id)
        if not session:
            return
        session.state = "cooling"
        try:
            for tab in session.tabs.values():
                try:
                    tab.url = tab.page.url
                    tab.title = await tab.page.title()
                except:
                    pass
            if session.browser:
                await session.browser.close()
            session.browser = None
            session.context = None
            for tab in session.tabs.values():
                tab.page = None
            session.state = "cold"
        except:
            session.state = "cold"

    async def close_session(self, session_id: str):
        await self.cool_session(session_id)
        self.sessions.pop(session_id, None)

    async def _get_active_page(self, session_id: str) -> tuple:
        session = self.sessions.get(session_id)
        if not session:
            raise Exception(f"Session {session_id} not found")
        if session.state == "cold":
            session = await self.warm_session(session_id)
        if not session.page:
            raise Exception("No active tab/page available")
        session.state = "active"
        session.last_activity = time.time()
        return session, session.page

    # ==================== TAB MANAGEMENT ====================

    async def new_tab(self, session_id: str, url: Optional[str] = None) -> Dict:
        session = self.sessions.get(session_id)
        if not session or not session.context:
            raise Exception("No active session")
        session.last_activity = time.time()

        page = await session.context.new_page()
        tab_id = f"tab-{len(session.tabs)}"
        tab = TabInfo(tab_id, page)
        session.tabs[tab_id] = tab
        session.active_tab_id = tab_id

        result = {"success": True, "tab_id": tab_id, "tab_count": len(session.tabs)}

        if url:
            try:
                response = await page.goto(url, wait_until="domcontentloaded", timeout=15000)
                tab.url = page.url
                tab.title = await page.title()
                tab.last_screenshot = await self._capture_screenshot(page)
                result["url"] = tab.url
                result["title"] = tab.title
                result["has_screenshot"] = True
            except Exception as e:
                result["error"] = str(e)

        session.record_step("new_tab", {"url": url, "tab_id": tab_id})
        session.state = "warm"
        return result

    async def switch_tab(self, session_id: str, tab_id: str) -> Dict:
        session = self.sessions.get(session_id)
        if not session:
            raise Exception("No active session")
        if tab_id not in session.tabs:
            raise Exception(f"Tab {tab_id} not found")

        session.active_tab_id = tab_id
        session.last_activity = time.time()
        tab = session.tabs[tab_id]

        try:
            await tab.page.bring_to_front()
            tab.url = tab.page.url
            tab.title = await tab.page.title()
            tab.last_screenshot = await self._capture_screenshot(tab.page)
        except:
            pass

        session.record_step("switch_tab", {"tab_id": tab_id})
        return {"success": True, "tab_id": tab_id, "url": tab.url, "title": tab.title}

    async def close_tab(self, session_id: str, tab_id: str) -> Dict:
        session = self.sessions.get(session_id)
        if not session:
            raise Exception("No active session")
        if tab_id not in session.tabs:
            raise Exception(f"Tab {tab_id} not found")
        if len(session.tabs) <= 1:
            raise Exception("Cannot close last tab")

        tab = session.tabs.pop(tab_id)
        try:
            await tab.page.close()
        except:
            pass

        if session.active_tab_id == tab_id:
            session.active_tab_id = list(session.tabs.keys())[0]

        session.record_step("close_tab", {"tab_id": tab_id})
        return {"success": True, "closed": tab_id, "active_tab": session.active_tab_id, "tab_count": len(session.tabs)}

    async def list_tabs(self, session_id: str) -> Dict:
        session = self.sessions.get(session_id)
        if not session:
            return {"tabs": [], "active_tab": None}
        return {
            "tabs": [t.to_dict() for t in session.tabs.values()],
            "active_tab": session.active_tab_id,
        }

    # ==================== BROWSER ACTIONS ====================

    async def navigate(self, session_id: str, url: str) -> Dict:
        session, page = await self._get_active_page(session_id)
        try:
            response = await page.goto(url, wait_until="domcontentloaded", timeout=20000)
            tab = session.active_tab
            if tab:
                tab.url = page.url
                tab.title = await page.title()
                tab.last_screenshot = await self._capture_screenshot(page)
                tab.accessibility_tree = await self._get_accessibility_tree(page)

            session.record_step("navigate", {"url": url})
            session.history.append({"action": "navigate", "url": url, "timestamp": datetime.utcnow().isoformat()})
            session.state = "warm"

            return {
                "success": True,
                "url": page.url,
                "title": await page.title(),
                "status": response.status if response else None,
                "screenshot": tab.last_screenshot if tab else "",
                "accessibility_summary": self._summarize_a11y(tab.accessibility_tree if tab else {}),
            }
        except Exception as e:
            session.state = "warm"
            return {"success": False, "error": str(e)}

    async def act(self, session_id: str, action: str) -> Dict:
        session, page = await self._get_active_page(session_id)
        try:
            a11y_tree = await self._get_accessibility_tree(page)
            result = await self._execute_action(page, action, a11y_tree)
            await page.wait_for_timeout(1000)

            tab = session.active_tab
            if tab:
                tab.last_screenshot = await self._capture_screenshot(page)
                tab.accessibility_tree = await self._get_accessibility_tree(page)
                tab.url = page.url
                tab.title = await page.title()

            session.record_step("act", {"action_description": action, "result": result.get("action_taken", "")})
            session.state = "warm"

            return {
                "success": True,
                "action_taken": result.get("action_taken", ""),
                "url": page.url,
                "screenshot": tab.last_screenshot if tab else "",
                "accessibility_summary": self._summarize_a11y(tab.accessibility_tree if tab else {}),
            }
        except Exception as e:
            session.state = "warm"
            return {"success": False, "error": str(e)}

    async def _execute_action(self, page: Page, action: str, a11y_tree: Dict) -> Dict:
        action_lower = action.lower().strip()

        if action_lower.startswith("click"):
            target = action_lower.replace("click", "").replace("on", "").replace("the", "").strip()
            try:
                locator = page.get_by_role("link", name=target).or_(
                    page.get_by_role("button", name=target)
                ).or_(page.get_by_text(target, exact=False))
                await locator.first.click(timeout=5000)
                return {"action_taken": f"Clicked '{target}'"}
            except:
                try:
                    await page.click(f"text={target}", timeout=5000)
                    return {"action_taken": f"Clicked text '{target}'"}
                except:
                    return {"action_taken": f"Could not find '{target}'"}

        elif any(kw in action_lower for kw in ["type", "fill", "enter"]):
            parts = action_lower.split(" into ") if " into " in action_lower else action_lower.split(" in ")
            if len(parts) >= 2:
                text_part = parts[0]
                for kw in ["type", "fill", "enter"]:
                    text_part = text_part.replace(kw, "")
                text = text_part.strip().strip('"\'')
                target = parts[1].strip()
                try:
                    locator = page.get_by_role("textbox", name=target).or_(
                        page.get_by_placeholder(target)
                    ).or_(page.locator(f"input[name*='{target}'], textarea[name*='{target}']"))
                    await locator.first.fill(text, timeout=5000)
                    return {"action_taken": f"Typed '{text}' into '{target}'"}
                except:
                    try:
                        await page.locator("input:visible, textarea:visible").first.fill(text, timeout=5000)
                        return {"action_taken": f"Typed '{text}' into first input"}
                    except:
                        return {"action_taken": f"Could not find input for '{target}'"}
            else:
                text = action_lower
                for kw in ["type", "fill", "enter"]:
                    text = text.replace(kw, "")
                text = text.strip().strip('"\'')
                try:
                    await page.locator("input:visible, textarea:visible").first.fill(text, timeout=5000)
                    return {"action_taken": f"Typed '{text}'"}
                except:
                    return {"action_taken": "Could not find input"}

        elif "scroll" in action_lower:
            direction = "down" if "down" in action_lower else "up"
            amount = -500 if direction == "up" else 500
            await page.evaluate(f"window.scrollBy(0, {amount})")
            return {"action_taken": f"Scrolled {direction}"}

        elif "back" in action_lower:
            await page.go_back()
            return {"action_taken": "Navigated back"}

        elif "press enter" in action_lower or "submit" in action_lower:
            await page.keyboard.press("Enter")
            return {"action_taken": "Pressed Enter"}

        elif "wait" in action_lower:
            await page.wait_for_timeout(2000)
            return {"action_taken": "Waited 2 seconds"}

        elif "select" in action_lower:
            # Try to select from dropdown
            parts = action_lower.replace("select", "").strip().split(" from ")
            if len(parts) >= 2:
                value, selector = parts[0].strip(), parts[1].strip()
                try:
                    await page.select_option(f"select", label=value, timeout=5000)
                    return {"action_taken": f"Selected '{value}'"}
                except:
                    return {"action_taken": f"Could not select '{value}'"}
            return {"action_taken": "Unclear select action"}

        else:
            return {"action_taken": f"Unknown action: {action}"}

    async def extract(self, session_id: str, query: str) -> Dict:
        session, page = await self._get_active_page(session_id)
        try:
            a11y_tree = await self._get_accessibility_tree(page)
            title = await page.title()
            url = page.url

            text_content = await page.evaluate("""
                () => {
                    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT, null);
                    const texts = [];
                    let node;
                    while (node = walker.nextNode()) {
                        const text = node.textContent.trim();
                        if (text && text.length > 1) texts.push(text);
                    }
                    return texts.slice(0, 100).join('\\n');
                }
            """)

            links = await page.evaluate("""
                () => Array.from(document.querySelectorAll('a[href]')).slice(0, 20)
                    .map(a => ({text: a.textContent.trim(), href: a.href})).filter(l => l.text)
            """)

            forms = await page.evaluate("""
                () => Array.from(document.querySelectorAll('input, textarea, select')).slice(0, 20)
                    .map(el => ({type: el.type || el.tagName.toLowerCase(), name: el.name || el.id || el.placeholder || '', value: el.value || ''}))
            """)

            images = await page.evaluate("""
                () => Array.from(document.querySelectorAll('img[src]')).slice(0, 10)
                    .map(img => ({src: img.src, alt: img.alt || '', width: img.naturalWidth, height: img.naturalHeight}))
            """)

            session.record_step("extract", {"query": query})
            session.state = "warm"

            return {
                "success": True, "url": url, "title": title,
                "text_content": text_content[:2000],
                "links": links, "forms": forms, "images": images,
                "accessibility_summary": self._summarize_a11y(a11y_tree),
            }
        except Exception as e:
            session.state = "warm"
            return {"success": False, "error": str(e)}

    async def observe(self, session_id: str) -> Dict:
        session, page = await self._get_active_page(session_id)
        try:
            tab = session.active_tab
            screenshot = await self._capture_screenshot(page)
            a11y_tree = await self._get_accessibility_tree(page)
            if tab:
                tab.last_screenshot = screenshot
                tab.accessibility_tree = a11y_tree

            interactive = await page.evaluate("""
                () => {
                    const elements = [];
                    document.querySelectorAll('a, button, input, textarea, select, [role="button"], [role="link"], [onclick]').forEach((el, i) => {
                        if (i > 30) return;
                        const rect = el.getBoundingClientRect();
                        if (rect.width === 0 || rect.height === 0) return;
                        elements.push({
                            tag: el.tagName.toLowerCase(),
                            role: el.getAttribute('role') || '',
                            text: (el.textContent || el.value || el.placeholder || el.getAttribute('aria-label') || '').trim().slice(0, 100),
                            type: el.type || '', id: el.id || '', name: el.name || '', href: el.href || '',
                            bounds: {x: Math.round(rect.x), y: Math.round(rect.y), w: Math.round(rect.width), h: Math.round(rect.height)}
                        });
                    });
                    return elements;
                }
            """)

            session.state = "warm"
            return {
                "success": True, "url": page.url, "title": await page.title(),
                "screenshot": screenshot, "interactive_elements": interactive,
                "accessibility_tree": a11y_tree,
                "accessibility_summary": self._summarize_a11y(a11y_tree),
            }
        except Exception as e:
            session.state = "warm"
            return {"success": False, "error": str(e)}

    async def screenshot(self, session_id: str) -> Dict:
        session, page = await self._get_active_page(session_id)
        try:
            screenshot = await self._capture_screenshot(page)
            tab = session.active_tab
            if tab:
                tab.last_screenshot = screenshot
            session.state = "warm"
            return {"success": True, "screenshot": screenshot, "url": page.url, "title": await page.title()}
        except Exception as e:
            session.state = "warm"
            return {"success": False, "error": str(e)}

    # ==================== VISION / PERCEPTION ====================

    async def get_screenshot_base64(self, session_id: str) -> Optional[str]:
        """Get current screenshot as base64 for LLM vision input."""
        session = self.sessions.get(session_id)
        if not session:
            return None
        tab = session.active_tab
        if tab and tab.page:
            try:
                raw = await tab.page.screenshot(type="jpeg", quality=70, full_page=False)
                return base64.b64encode(raw).decode('utf-8')
            except:
                pass
        if tab and tab.last_screenshot:
            return tab.last_screenshot
        return None

    async def get_page_context(self, session_id: str) -> Dict:
        """Get rich page context for LLM analysis - combines visual + structural data."""
        session, page = await self._get_active_page(session_id)
        try:
            screenshot_b64 = await self._capture_screenshot(page)
            a11y_tree = await self._get_accessibility_tree(page)
            title = await page.title()
            url = page.url

            # Get page metadata
            meta = await page.evaluate("""
                () => ({
                    title: document.title,
                    description: document.querySelector('meta[name="description"]')?.content || '',
                    ogTitle: document.querySelector('meta[property="og:title"]')?.content || '',
                    ogDescription: document.querySelector('meta[property="og:description"]')?.content || '',
                    canonical: document.querySelector('link[rel="canonical"]')?.href || '',
                    lang: document.documentElement.lang || '',
                    headings: Array.from(document.querySelectorAll('h1,h2,h3')).slice(0, 15).map(h => ({
                        level: h.tagName, text: h.textContent.trim().slice(0, 100)
                    })),
                    formCount: document.querySelectorAll('form').length,
                    linkCount: document.querySelectorAll('a').length,
                    imageCount: document.querySelectorAll('img').length,
                    inputCount: document.querySelectorAll('input, textarea').length,
                })
            """)

            # Get main content text
            main_text = await page.evaluate("""
                () => {
                    const main = document.querySelector('main, article, [role="main"], .content, #content');
                    if (main) return main.textContent.trim().slice(0, 1500);
                    return document.body.textContent.trim().slice(0, 1500);
                }
            """)

            session.state = "warm"
            return {
                "success": True,
                "screenshot_base64": screenshot_b64,
                "url": url,
                "title": title,
                "meta": meta,
                "main_text": main_text,
                "accessibility_summary": self._summarize_a11y(a11y_tree),
                "a11y_tree": a11y_tree,
            }
        except Exception as e:
            session.state = "warm"
            return {"success": False, "error": str(e)}

    # ==================== MACRO RECORDING ====================

    def start_recording(self, session_id: str) -> Dict:
        session = self.sessions.get(session_id)
        if not session:
            return {"success": False, "error": "No session"}
        session.recording = True
        session.recorded_steps = []
        return {"success": True, "message": "Recording started"}

    def stop_recording(self, session_id: str) -> Dict:
        session = self.sessions.get(session_id)
        if not session:
            return {"success": False, "error": "No session"}
        session.recording = False
        steps = [s.to_dict() for s in session.recorded_steps]
        return {"success": True, "steps_count": len(steps), "steps": steps}

    def save_macro(self, name: str, description: str, steps: List[Dict]) -> Dict:
        macro_id = str(uuid.uuid4())[:8]
        macro = {
            "id": macro_id,
            "name": name,
            "description": description,
            "steps": steps,
            "created_at": datetime.utcnow().isoformat(),
            "run_count": 0,
        }
        self.macros[macro_id] = macro
        return macro

    async def play_macro(self, session_id: str, macro_id: str, delay: float = 0.5) -> Dict:
        """Execute a saved macro step by step."""
        session = self.sessions.get(session_id)
        if not session:
            return {"success": False, "error": "No session"}
        macro = self.macros.get(macro_id)
        if not macro:
            return {"success": False, "error": "Macro not found"}

        results = []
        for step in macro["steps"]:
            action = step["action"]
            params = step["params"]
            try:
                if action == "navigate":
                    r = await self.navigate(session_id, params.get("url", ""))
                elif action == "act":
                    r = await self.act(session_id, params.get("action_description", ""))
                elif action == "new_tab":
                    r = await self.new_tab(session_id, params.get("url"))
                elif action == "switch_tab":
                    r = await self.switch_tab(session_id, params.get("tab_id", ""))
                elif action == "close_tab":
                    r = await self.close_tab(session_id, params.get("tab_id", ""))
                elif action == "extract":
                    r = await self.extract(session_id, params.get("query", ""))
                else:
                    r = {"skipped": True, "action": action}

                # Remove screenshot from results to save memory
                r.pop("screenshot", None)
                results.append({"step": action, "result": r})
            except Exception as e:
                results.append({"step": action, "error": str(e)})

            await asyncio.sleep(delay)

        macro["run_count"] += 1
        return {"success": True, "macro": macro["name"], "steps_executed": len(results), "results": results}

    def list_macros(self) -> List[Dict]:
        return list(self.macros.values())

    def delete_macro(self, macro_id: str) -> bool:
        return self.macros.pop(macro_id, None) is not None

    # ==================== HELPERS ====================

    async def _capture_screenshot(self, page: Page) -> str:
        try:
            raw = await page.screenshot(type="jpeg", quality=60, full_page=False)
            return base64.b64encode(raw).decode('utf-8')
        except:
            return ""

    async def _get_accessibility_tree(self, page: Page) -> Dict:
        try:
            snapshot = await page.accessibility.snapshot()
            return snapshot or {}
        except:
            return {}

    def _summarize_a11y(self, tree: Dict, depth: int = 0, max_depth: int = 3) -> str:
        if not tree or depth > max_depth:
            return ""
        parts = []
        role = tree.get("role", "")
        name = tree.get("name", "")
        value = tree.get("value", "")
        if name or role:
            indent = "  " * depth
            label = f"{indent}[{role}]" if role else indent
            if name:
                label += f" {name}"
            if value:
                label += f" = {value}"
            parts.append(label)
        for child in tree.get("children", []):
            child_summary = self._summarize_a11y(child, depth + 1, max_depth)
            if child_summary:
                parts.append(child_summary)
        return "\n".join(parts[:50])

    # ==================== STATUS ====================

    def get_status(self) -> Dict:
        return {
            "active_sessions": len(self.sessions),
            "sessions": {sid: s.to_dict() for sid, s in self.sessions.items()},
            "playwright_ready": self._playwright_instance is not None,
            "macros_count": len(self.macros),
        }

    async def shutdown(self):
        for sid in list(self.sessions.keys()):
            await self.close_session(sid)
        if self._playwright_instance:
            await self.playwright.stop()
            self._playwright_instance = None
        if self._cleanup_task:
            self._cleanup_task.cancel()


# Singleton
ghostwright = GhostWrightEngine()
