"""Rotate across multiple browser sessions to distribute load and handle rate limits."""

import asyncio
import logging
import random
import time
from typing import Optional

from playwright.async_api import Page

from .human import random_mouse_move, human_delay

logger = logging.getLogger(__name__)

# How long a session stays in cooldown after a rate limit (seconds)
_DEFAULT_COOLDOWN = 300  # 5 minutes


class SessionRotator:
    """Manages multiple Playwright pages and rotates between them.

    When a session hits a rate limit, it's placed in cooldown and the
    rotator automatically switches to the next healthy session.  This
    distributes requests across accounts so each one looks like a
    normal user with moderate activity.

    Usage:
        rotator = SessionRotator()
        rotator.add("session-1", page1)
        rotator.add("session-2", page2)

        page = rotator.get_page()           # round-robin
        page = rotator.get_page()           # next session
        rotator.mark_rate_limited("session-1")  # cooldown
        page = rotator.get_page()           # skips session-1
    """

    def __init__(self, cooldown_secs: int = _DEFAULT_COOLDOWN):
        self._pages: dict[str, Page] = {}
        self._order: list[str] = []
        self._index: int = 0
        self._cooldowns: dict[str, float] = {}  # session_id -> cooldown_until timestamp
        self._cooldown_secs = cooldown_secs

    def add(self, session_id: str, page: Page) -> None:
        """Register a session's page for rotation."""
        self._pages[session_id] = page
        if session_id not in self._order:
            self._order.append(session_id)
        logger.info("SessionRotator: added session %s (total: %d)", session_id, len(self._order))

    @property
    def session_count(self) -> int:
        return len(self._order)

    @property
    def available_count(self) -> int:
        """Number of sessions not currently in cooldown."""
        now = time.time()
        return sum(1 for sid in self._order if self._cooldowns.get(sid, 0) <= now)

    def get_page(self) -> Page:
        """Return the next available page via round-robin, skipping cooled-down sessions.

        Raises RuntimeError if all sessions are in cooldown.
        """
        if not self._order:
            raise RuntimeError("No sessions registered in rotator")

        now = time.time()
        checked = 0

        while checked < len(self._order):
            sid = self._order[self._index % len(self._order)]
            self._index += 1
            checked += 1

            cooldown_until = self._cooldowns.get(sid, 0)
            if cooldown_until <= now:
                logger.debug("SessionRotator: using session %s", sid)
                return self._pages[sid]

        # All sessions are cooling down — find the one that expires soonest
        soonest_sid = min(self._order, key=lambda s: self._cooldowns.get(s, 0))
        wait = self._cooldowns[soonest_sid] - now
        raise RuntimeError(
            f"All {len(self._order)} sessions are rate-limited. "
            f"Nearest cooldown expires in {int(wait)}s."
        )

    def get_current_session_id(self) -> str:
        """Return the session_id of the most recently served page."""
        idx = (self._index - 1) % len(self._order)
        return self._order[idx]

    def mark_rate_limited(self, session_id: Optional[str] = None) -> None:
        """Put a session into cooldown. Defaults to the current session."""
        sid = session_id or self.get_current_session_id()
        until = time.time() + self._cooldown_secs
        self._cooldowns[sid] = until
        logger.warning(
            "SessionRotator: session %s rate-limited, cooldown %ds (available: %d/%d)",
            sid, self._cooldown_secs, self.available_count, len(self._order),
        )

    async def wait_for_any_available(self) -> None:
        """Block until at least one session exits cooldown."""
        now = time.time()
        soonest = min(self._cooldowns.get(s, 0) for s in self._order)
        wait = max(0, soonest - now)
        if wait > 0:
            logger.info("SessionRotator: all sessions cooling down, waiting %.0fs...", wait)
            await asyncio.sleep(wait + random.uniform(5, 15))

    async def switch_with_delay(self) -> Page:
        """Get next page with a human-like pause to simulate switching accounts."""
        await human_delay(2.0, 5.0)
        page = self.get_page()
        await random_mouse_move(page)
        return page
