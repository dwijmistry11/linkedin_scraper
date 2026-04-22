"""Human-like behavior helpers to avoid bot detection."""

import asyncio
import random
import logging
from playwright.async_api import Page

logger = logging.getLogger(__name__)


async def human_delay(min_sec: float = 1.0, max_sec: float = 3.0) -> None:
    """Sleep for a random duration to mimic human reading/thinking time."""
    delay = random.uniform(min_sec, max_sec)
    await asyncio.sleep(delay)


async def human_short_delay() -> None:
    """Brief pause like between micro-interactions (0.3–1.2s)."""
    await asyncio.sleep(random.uniform(0.3, 1.2))


async def human_read_delay() -> None:
    """Simulate reading a page (2–5s)."""
    await asyncio.sleep(random.uniform(2.0, 5.0))


async def human_between_pages() -> None:
    """Delay between navigating to different pages (5–12s)."""
    await asyncio.sleep(random.uniform(5.0, 12.0))


async def human_between_profiles() -> None:
    """Longer delay between scraping different profiles (8–18s)."""
    await asyncio.sleep(random.uniform(8.0, 18.0))


async def random_mouse_move(page: Page) -> None:
    """Move mouse to a random position on the page, like an idle user."""
    try:
        vw = page.viewport_size
        if not vw:
            return
        x = random.randint(100, vw["width"] - 100)
        y = random.randint(100, vw["height"] - 100)
        # Move in small steps to look natural
        await page.mouse.move(x, y, steps=random.randint(5, 15))
    except Exception:
        pass


async def human_scroll(page: Page, direction: str = "down", distance: int = 0) -> None:
    """Scroll the page in a human-like way — variable speed, partial scrolls."""
    try:
        if distance == 0:
            distance = random.randint(200, 600)

        if direction == "up":
            distance = -distance

        # Scroll in 2-4 smaller chunks with tiny pauses
        chunks = random.randint(2, 4)
        chunk_size = distance // chunks

        for _ in range(chunks):
            await page.mouse.wheel(0, chunk_size)
            await asyncio.sleep(random.uniform(0.1, 0.4))

    except Exception:
        pass


async def human_click(page: Page, locator, timeout: float = 5000) -> bool:
    """Click an element with human-like approach: hover first, small pause, then click."""
    try:
        await locator.hover(timeout=timeout)
        await asyncio.sleep(random.uniform(0.2, 0.6))
        await locator.click(timeout=timeout)
        return True
    except Exception:
        return False


async def human_type(page: Page, selector: str, text: str) -> None:
    """Type text character by character with random inter-key delays."""
    try:
        element = page.locator(selector).first
        await element.click()
        for char in text:
            await page.keyboard.type(char, delay=random.randint(50, 180))
    except Exception:
        pass
