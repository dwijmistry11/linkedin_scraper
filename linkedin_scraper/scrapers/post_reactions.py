"""Scraper that extracts users who reacted to or reposted a LinkedIn post."""

import asyncio
import logging
import random
import re
from typing import List, Optional

from playwright.async_api import Page, TimeoutError as PlaywrightTimeoutError

from ..callbacks import ProgressCallback, SilentCallback
from ..core.human import (
    human_click,
    human_delay,
    human_read_delay,
    human_short_delay,
    random_mouse_move,
)
from ..models.post import PostEngagementUser
from .base import BaseScraper

logger = logging.getLogger(__name__)


class PostReactionsScraper(BaseScraper):
    """Extract users who reacted to or reposted a specific LinkedIn post."""

    def __init__(self, page: Page, callback: Optional[ProgressCallback] = None):
        super().__init__(page, callback or SilentCallback())

    async def scrape(self, post_url: str, max_users: int = 100) -> List[PostEngagementUser]:
        """
        Navigate to a post and extract users who reacted and reposted.

        Args:
            post_url: Full LinkedIn post URL (e.g. https://www.linkedin.com/feed/update/urn:li:activity:123/)
            max_users: Maximum number of users to extract per engagement type.

        Returns:
            List of PostEngagementUser with engagement_type "reaction" or "repost".
        """
        logger.info("Extracting engaged users from post: %s", post_url)
        users: List[PostEngagementUser] = []

        await self.navigate_and_wait(post_url)
        await human_read_delay()
        await random_mouse_move(self.page)
        await self.close_modals()

        # Extract reactors
        reactors = await self._extract_reactors(max_users)
        users.extend(reactors)
        logger.info("Extracted %d reactors", len(reactors))

        # Pause between reaction and repost extraction
        await human_delay(2.0, 4.0)
        await random_mouse_move(self.page)

        # Extract reposters
        reposters = await self._extract_reposters(max_users)
        users.extend(reposters)
        logger.info("Extracted %d reposters", len(reposters))

        return users

    # ── Reactors ──────────────────────────────────────────────────

    async def _extract_reactors(self, max_users: int) -> List[PostEngagementUser]:
        """Click the reactions count to open the modal and extract users."""
        # Find and click the reactions count element
        reactions_btn = self.page.locator(
            'button[aria-label*="reaction"], '
            '[class*="social-details-social-counts__reactions"], '
            'button[aria-label*="like"], '
            'span[class*="reactions-count"]'
        ).first

        try:
            if not await reactions_btn.is_visible(timeout=3000):
                logger.debug("No reactions button found")
                return []
        except PlaywrightTimeoutError:
            return []

        if not await human_click(self.page, reactions_btn):
            logger.debug("Could not click reactions button")
            return []

        await human_delay(2.0, 4.0)

        users = await self._extract_users_from_modal("reaction", max_users)

        await self._close_modal()

        return users

    # ── Reposters ─────────────────────────────────────────────────

    async def _extract_reposters(self, max_users: int) -> List[PostEngagementUser]:
        """Click the reposts count to open the modal and extract users."""
        reposts_btn = self.page.locator(
            'button[aria-label*="repost"]'
        ).first

        try:
            if not await reposts_btn.is_visible(timeout=3000):
                logger.debug("No reposts button found")
                return []
        except PlaywrightTimeoutError:
            return []

        if not await human_click(self.page, reposts_btn):
            logger.debug("Could not click reposts button")
            return []

        await human_delay(2.0, 4.0)

        users = await self._extract_users_from_modal("repost", max_users)

        await self._close_modal()

        return users

    # ── Modal extraction ──────────────────────────────────────────

    async def _extract_users_from_modal(
        self, engagement_type: str, max_users: int
    ) -> List[PostEngagementUser]:
        """Extract user info from the currently open reactions/reposts modal."""
        users: List[PostEngagementUser] = []
        seen_urls: set[str] = set()

        # Wait for modal to appear
        modal = self.page.locator(
            '[role="dialog"], '
            '.artdeco-modal, '
            '.social-details-reactors-modal, '
            '[class*="reactors-modal"], '
            '[class*="repost-modal"]'
        ).first

        try:
            await modal.wait_for(timeout=5000)
        except PlaywrightTimeoutError:
            logger.debug("No modal appeared for %s", engagement_type)
            return []

        # Scroll the modal content to load all users
        scroll_attempts = 0
        max_scroll_attempts = max_users // 5 + 3  # rough estimate

        while len(users) < max_users and scroll_attempts < max_scroll_attempts:
            new_users = await self._parse_modal_users(modal, engagement_type, seen_urls)
            users.extend(new_users)

            if not new_users and scroll_attempts > 0:
                # No new users after scrolling — we've loaded them all
                break

            # Scroll within the modal with human-like timing
            await self._scroll_modal(modal)
            await human_delay(1.5, 3.0)
            scroll_attempts += 1

        return users[:max_users]

    async def _parse_modal_users(
        self, modal, engagement_type: str, seen_urls: set[str]
    ) -> List[PostEngagementUser]:
        """Parse user entries from the modal DOM."""
        new_users: List[PostEngagementUser] = []

        # Extract via JavaScript for robustness across LinkedIn layout variants
        entries = await self.page.evaluate('''(modalSelector) => {
            const modal = document.querySelector(
                '[role="dialog"], .artdeco-modal, [class*="reactors-modal"], [class*="repost-modal"]'
            );
            if (!modal) return [];

            const results = [];
            // Look for user list items — LinkedIn uses various structures
            const items = modal.querySelectorAll(
                '[class*="entity-result"], ' +
                '[class*="reactor-container"], ' +
                '[class*="social-details-reactors-tab-body-list-item"], ' +
                'li[class*="list-style-none"], ' +
                '.artdeco-list__item, ' +
                'ul li'
            );

            for (const item of items) {
                // Find the profile link
                const link = item.querySelector(
                    'a[href*="/in/"], a[href*="miniProfile"]'
                );
                const profileUrl = link ? link.href : null;

                // Find name — usually in a span or strong inside the link
                let name = '';
                const nameEl = item.querySelector(
                    '[class*="actor-name"], ' +
                    '[class*="entity-result__title"] span, ' +
                    'span[dir="ltr"], ' +
                    'span[aria-hidden="true"]'
                );
                if (nameEl) {
                    name = nameEl.innerText?.trim() || '';
                }
                // Fallback: use link text
                if (!name && link) {
                    name = link.innerText?.trim().split('\\n')[0] || '';
                }

                if (!name) continue;

                // Find headline
                let headline = '';
                const headlineEl = item.querySelector(
                    '[class*="actor-supplement"], ' +
                    '[class*="entity-result__primary-subtitle"], ' +
                    '[class*="subline-level-1"], ' +
                    'p[class*="text-body-small"]'
                );
                if (headlineEl) {
                    headline = headlineEl.innerText?.trim() || '';
                }

                results.push({
                    name: name.substring(0, 200),
                    headline: headline.substring(0, 300),
                    profileUrl: profileUrl
                });
            }

            return results;
        }''', None)

        for entry in entries:
            url = entry.get("profileUrl") or ""
            # Normalize URL
            if url and "/in/" in url:
                url = re.sub(r'\?.*$', '', url)  # strip query params

            if url and url in seen_urls:
                continue
            if url:
                seen_urls.add(url)

            name = entry.get("name", "").strip()
            if not name:
                continue

            new_users.append(PostEngagementUser(
                name=name,
                headline=entry.get("headline") or None,
                profile_url=url or None,
                engagement_type=engagement_type,
            ))

        return new_users

    async def _scroll_modal(self, modal) -> None:
        """Scroll within the modal to trigger lazy loading."""
        try:
            await self.page.evaluate('''() => {
                const modal = document.querySelector(
                    '[role="dialog"], .artdeco-modal, [class*="reactors-modal"]'
                );
                if (!modal) return;
                // Find the scrollable container inside the modal
                const scrollable = modal.querySelector(
                    '[class*="modal__content"], ' +
                    '[class*="artdeco-modal__content"], ' +
                    '[style*="overflow"]'
                ) || modal;
                scrollable.scrollTop = scrollable.scrollHeight;
            }''')
        except Exception:
            pass
        await human_delay(1.0, 2.5)

    async def _close_modal(self) -> None:
        """Close the currently open modal."""
        try:
            close_btn = self.page.locator(
                '[role="dialog"] button[aria-label="Dismiss"], '
                '[role="dialog"] button[aria-label="Close"], '
                'button.artdeco-modal__dismiss, '
                '[class*="modal"] button[aria-label="Dismiss"]'
            ).first
            if await close_btn.is_visible(timeout=2000):
                await human_click(self.page, close_btn)
                await human_short_delay()
        except Exception:
            # Fallback: press Escape
            try:
                await self.page.keyboard.press("Escape")
                await human_short_delay()
            except Exception:
                pass
