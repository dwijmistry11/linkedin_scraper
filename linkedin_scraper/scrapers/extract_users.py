"""Orchestrator scraper: extract engaged users from a company's posts.

Supports session rotation — when given a SessionRotator with multiple
LinkedIn sessions, it distributes work across them and automatically
switches to another session on rate limit.
"""

import asyncio
import logging
import random
from typing import List, Optional

from playwright.async_api import Page

from ..callbacks import ProgressCallback, SilentCallback
from ..core.exceptions import RateLimitError
from ..core.human import human_between_pages, human_between_profiles, human_delay, random_mouse_move
from ..core.session_rotator import SessionRotator
from ..models.post import ExtractUsersResult, PostEngagementUser
from ..models.person import Person
from .base import BaseScraper
from .company_posts import CompanyPostsScraper
from .post_reactions import PostReactionsScraper
from .person import PersonScraper

logger = logging.getLogger(__name__)

# After how many consecutive operations to take a longer "coffee break"
_BATCH_SIZE = 3


class ExtractUsersFromPostsScraper(BaseScraper):
    """
    Full pipeline: company URL -> posts -> reaction/repost users -> (optional) profiles.

    Single-session usage:
        scraper = ExtractUsersFromPostsScraper(page, callback)
        result = await scraper.scrape(company_url)

    Multi-session usage (rotation):
        rotator = SessionRotator()
        rotator.add("s1", page1)
        rotator.add("s2", page2)
        scraper = ExtractUsersFromPostsScraper(page1, callback, rotator=rotator)
        result = await scraper.scrape(company_url)
    """

    def __init__(
        self,
        page: Page,
        callback: Optional[ProgressCallback] = None,
        rotator: Optional[SessionRotator] = None,
    ):
        super().__init__(page, callback or SilentCallback())
        self._rotator = rotator

    def _get_page(self) -> Page:
        """Get the next page — from rotator if available, else the single page."""
        if self._rotator and self._rotator.session_count > 1:
            return self._rotator.get_page()
        return self.page

    async def _handle_rate_limit(self, context: str) -> None:
        """Called when a rate limit is hit. Rotates session or waits."""
        if self._rotator and self._rotator.session_count > 1:
            self._rotator.mark_rate_limited()
            available = self._rotator.available_count
            if available > 0:
                logger.info("Rate limited during %s — rotating to next session (%d available)", context, available)
                await self.callback.on_progress(
                    f"Session rate-limited — switching to another ({available} available)...", -1
                )
                await human_delay(3.0, 6.0)
                return
            else:
                logger.warning("All sessions rate-limited during %s — waiting for cooldown", context)
                await self.callback.on_progress("All sessions cooling down — waiting...", -1)
                await self._rotator.wait_for_any_available()
                return

        # Single session — just wait
        wait = random.randint(60, 120)
        logger.warning("Rate limited during %s (single session). Waiting %ds...", context, wait)
        await self.callback.on_progress(f"Rate limited — pausing {wait}s...", -1)
        await asyncio.sleep(wait)

    async def scrape(
        self,
        company_url: str,
        posts_limit: int = 10,
        max_users_per_post: int = 100,
        scrape_profiles: bool = False,
    ) -> ExtractUsersResult:
        await self.callback.on_start("extract_users", company_url)

        if self._rotator and self._rotator.session_count > 1:
            await self.callback.on_progress(
                f"Using {self._rotator.session_count} sessions with rotation", 2
            )

        # ── Step 1: Scrape company posts (uses first available session) ──
        await self.callback.on_progress("Scraping company posts...", 5)
        page = self._get_page()
        posts_scraper = CompanyPostsScraper(page)
        posts = await posts_scraper.scrape(company_url, limit=posts_limit)
        await self.callback.on_progress(f"Found {len(posts)} posts", 15)

        if not posts:
            result = ExtractUsersResult(company_url=company_url, posts_scraped=0, users=[])
            await self.callback.on_complete("extract_users", result)
            return result

        # ── Step 2: Extract reactors/reposters from each post ──
        all_users: List[PostEngagementUser] = []
        seen_urls: set[str] = set()

        for i, post in enumerate(posts):
            if not post.linkedin_url:
                continue

            pct = 15 + int((i / len(posts)) * 65)
            await self.callback.on_progress(
                f"Extracting users from post {i + 1}/{len(posts)}...", pct
            )

            # Get a (possibly rotated) page for this post
            page = self._get_page()
            reactions_scraper = PostReactionsScraper(page)

            retries = 2 if (self._rotator and self._rotator.session_count > 1) else 1
            post_users: List[PostEngagementUser] = []

            for attempt in range(retries + 1):
                try:
                    post_users = await reactions_scraper.scrape(
                        post.linkedin_url, max_users=max_users_per_post
                    )
                    break  # success
                except RateLimitError:
                    await self._handle_rate_limit(f"post {i + 1}")
                    # Get a fresh page (might be a different session now)
                    page = self._get_page()
                    reactions_scraper = PostReactionsScraper(page)
                except Exception as e:
                    logger.warning("Failed to extract users from post %s: %s", post.linkedin_url, e)
                    break

            # Deduplicate
            for user in post_users:
                key = user.profile_url or user.name
                if key not in seen_urls:
                    seen_urls.add(key)
                    all_users.append(user)

            # Human-like pause between posts
            await human_between_pages()
            await random_mouse_move(page)

            # Batch break every few posts
            if (i + 1) % _BATCH_SIZE == 0 and i + 1 < len(posts):
                pause = random.randint(15, 30)
                logger.info("Batch break: pausing %ds after %d posts", pause, i + 1)
                await self.callback.on_progress(
                    f"Processed {i + 1}/{len(posts)} posts — brief pause...", pct
                )
                await asyncio.sleep(pause)

        await self.callback.on_progress(
            f"Extracted {len(all_users)} unique users from {len(posts)} posts", 80
        )

        # ── Step 3 (optional): Scrape full profiles ──
        profiles: List[Person] = []
        if scrape_profiles and all_users:
            users_with_url = [u for u in all_users if u.profile_url]

            for j, user in enumerate(users_with_url):
                pct = 80 + int((j / len(users_with_url)) * 18)
                await self.callback.on_progress(
                    f"Scraping profile {j + 1}/{len(users_with_url)}: {user.name}...", pct
                )

                page = self._get_page()
                person_scraper = PersonScraper(page)

                retries = 2 if (self._rotator and self._rotator.session_count > 1) else 1
                for attempt in range(retries + 1):
                    try:
                        person = await person_scraper.scrape(user.profile_url)
                        profiles.append(person)
                        break
                    except RateLimitError:
                        await self._handle_rate_limit(f"profile {j + 1}")
                        page = self._get_page()
                        person_scraper = PersonScraper(page)
                    except Exception as e:
                        logger.warning("Failed to scrape profile %s: %s", user.profile_url, e)
                        break

                # Human-like pause between profiles
                await human_between_profiles()

                # Batch break every few profiles
                if (j + 1) % _BATCH_SIZE == 0 and j + 1 < len(users_with_url):
                    pause = random.randint(20, 45)
                    logger.info("Profile batch break: pausing %ds", pause)
                    await self.callback.on_progress(
                        f"Scraped {j + 1}/{len(users_with_url)} profiles — brief pause...", pct
                    )
                    await asyncio.sleep(pause)

        result = ExtractUsersResult(
            company_url=company_url,
            posts_scraped=len(posts),
            users=all_users,
        )

        await self.callback.on_progress(
            f"Done: {len(all_users)} users from {len(posts)} posts", 100
        )
        await self.callback.on_complete("extract_users", result)
        return result
