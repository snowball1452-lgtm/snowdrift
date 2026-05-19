# ghostwright.py — Android/Chaquopy shim
# The real GhostWright uses Playwright (headless Chromium) which has no
# ARM64 Android binary. On-device, browser automation is handled by the
# Android WebView via the Kotlin accessibility layer instead.
# This stub preserves all import paths so server.py loads cleanly.

import logging
log = logging.getLogger(__name__)


class _GhostWrightStub:
    """No-op stub that returns clear errors instead of crashing."""

    async def open_tab(self, url: str, **kw):
        return {"error": "GhostWright unavailable on Android — use WebView via accessibility layer"}

    async def screenshot(self, tab_id: str = None, **kw):
        return {"error": "GhostWright unavailable on Android"}

    async def execute_js(self, *a, **kw):
        return {"error": "GhostWright unavailable on Android"}

    async def get_page_content(self, *a, **kw):
        return {"error": "GhostWright unavailable on Android"}

    async def close_tab(self, *a, **kw):
        return {"error": "GhostWright unavailable on Android"}

    async def list_tabs(self, *a, **kw):
        return []

    def get_stats(self):
        return {"status": "unavailable", "reason": "Android — no ARM Chromium"}

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        pass


ghostwright = _GhostWrightStub()
log.info("GhostWright: running Android shim (no Playwright)")
