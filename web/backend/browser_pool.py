"""Manages long-lived BrowserManager instances, one per LinkedIn session."""

import asyncio
import logging
from pathlib import Path
from typing import Optional

from linkedin_scraper import BrowserManager

logger = logging.getLogger(__name__)


class BrowserPool:
    """Pool of BrowserManager instances keyed by session_id.

    Each LinkedIn session gets its own Chromium browser so cookies/context
    stay isolated.  A per-session asyncio.Lock ensures that only one
    scraping operation uses a given browser page at a time.
    """

    def __init__(
        self,
        sessions_dir: Path,
        headless: bool = False,
        slow_mo: int = 0,
        max_sessions: int = 3,
    ):
        self.sessions_dir = sessions_dir
        self.headless = headless
        self.slow_mo = slow_mo
        self.max_sessions = max_sessions

        self._browsers: dict[str, BrowserManager] = {}
        self._locks: dict[str, asyncio.Lock] = {}

    # ── public API ────────────────────────────────────────────────

    async def get_browser(self, session_id: str, session_file: str) -> BrowserManager:
        """Return a running BrowserManager for *session_id*, starting one if needed."""
        if session_id not in self._browsers:
            if len(self._browsers) >= self.max_sessions:
                raise RuntimeError(
                    f"Maximum concurrent sessions ({self.max_sessions}) reached. "
                    "Close an existing session first."
                )
            browser = BrowserManager(headless=self.headless, slow_mo=self.slow_mo)
            await browser.start()
            session_path = Path(session_file)
            if session_path.exists():
                await browser.load_session(str(session_path))
            self._browsers[session_id] = browser
            self._locks[session_id] = asyncio.Lock()
            logger.info("Started browser for session %s", session_id)
        return self._browsers[session_id]

    def lock(self, session_id: str) -> asyncio.Lock:
        """Return the per-session lock (must call get_browser first)."""
        if session_id not in self._locks:
            self._locks[session_id] = asyncio.Lock()
        return self._locks[session_id]

    async def close_browser(self, session_id: str) -> None:
        """Shut down a specific session's browser."""
        browser = self._browsers.pop(session_id, None)
        self._locks.pop(session_id, None)
        if browser:
            await browser.close()
            logger.info("Closed browser for session %s", session_id)

    async def close_all(self) -> None:
        """Shut down every running browser (called at app shutdown)."""
        for sid in list(self._browsers):
            await self.close_browser(sid)

    async def is_authenticated(self, session_id: str, session_file: str) -> bool:
        """Start browser if needed, navigate to LinkedIn, and check login status."""
        from linkedin_scraper import is_logged_in

        browser = await self.get_browser(session_id, session_file)
        page = browser.page
        # Must navigate to LinkedIn so is_logged_in() can check URL and nav elements
        try:
            await page.goto("https://www.linkedin.com/feed/", wait_until="domcontentloaded", timeout=30000)
        except Exception as e:
            logger.warning("Failed to navigate to LinkedIn for auth check: %s", e)
            return False
        return await is_logged_in(page)

    @property
    def active_count(self) -> int:
        return len(self._browsers)
