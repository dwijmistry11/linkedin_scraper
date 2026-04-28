"""Orchestrates scraping operations as background tasks."""

import json
import logging
from datetime import datetime, timezone

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from linkedin_scraper import (
    CompanyPostsScraper,
    CompanyScraper,
    ExtractUsersFromPostsScraper,
    JobScraper,
    JobSearchScraper,
    PersonScraper,
)
from linkedin_scraper.core.session_rotator import SessionRotator

from ..browser_pool import BrowserPool
from ..database import async_session
from ..models import ScrapeJob, ScrapeResult
from ..ws_callback import WebSocketCallback

logger = logging.getLogger(__name__)


async def run_scrape(
    pool: BrowserPool,
    job_id: str,
    session_id: str,
    session_file: str,
    scrape_type: str,
    params: dict,
) -> None:
    """Background task: acquire browser, run scraper, store result."""
    async with async_session() as db:
        callback = WebSocketCallback(job_id, db)

        lock = pool.lock(session_id)
        async with lock:
            try:
                browser = await pool.get_browser(session_id, session_file)
                page = browser.page

                if scrape_type == "person":
                    scraper = PersonScraper(page, callback)
                    result = await scraper.scrape(params["url"])
                    result_json = result.model_dump_json()

                elif scrape_type == "company":
                    scraper = CompanyScraper(page, callback)
                    result = await scraper.scrape(params["url"])
                    result_json = result.model_dump_json()

                elif scrape_type == "job":
                    scraper = JobScraper(page, callback)
                    result = await scraper.scrape(params["url"])
                    result_json = result.model_dump_json()

                elif scrape_type == "job_search":
                    scraper = JobSearchScraper(page, callback)
                    result = await scraper.search(
                        keywords=params.get("keywords"),
                        location=params.get("location"),
                        limit=params.get("limit", 25),
                    )
                    # job_search returns list of URL strings
                    result_json = json.dumps(result)

                elif scrape_type == "company_posts":
                    scraper = CompanyPostsScraper(page, callback)
                    result = await scraper.scrape(
                        params["company_url"],
                        limit=params.get("limit", 10),
                    )
                    result_json = json.dumps([p.model_dump() for p in result])

                elif scrape_type == "extract_users":
                    scraper = ExtractUsersFromPostsScraper(page, callback)
                    result = await scraper.scrape(
                        params["company_url"],
                        posts_limit=params.get("posts_limit", 10),
                        scrape_profiles=params.get("scrape_profiles", False),
                    )
                    result_json = result.model_dump_json()

                else:
                    raise ValueError(f"Unknown scrape type: {scrape_type}")

                # Store result
                db.add(ScrapeResult(
                    job_id=job_id,
                    scrape_type=scrape_type,
                    result_data=result_json,
                ))
                await db.execute(
                    update(ScrapeJob)
                    .where(ScrapeJob.id == job_id)
                    .values(
                        status="completed",
                        progress_percent=100,
                        completed_at=datetime.now(timezone.utc),
                    )
                )
                await db.commit()

                await callback.on_complete(scrape_type, result)

                # Auto-sync to CRM if enabled
                await _auto_sync_to_crm(scrape_type, result_json)

            except Exception as e:
                logger.exception("Scrape job %s failed", job_id)
                await callback.on_error(e)
                try:
                    await db.execute(
                        update(ScrapeJob)
                        .where(ScrapeJob.id == job_id)
                        .values(status="failed", error_message=str(e))
                    )
                    await db.commit()
                except Exception:
                    pass


async def _auto_sync_to_crm(scrape_type: str, result_json: str) -> None:
    """If CRM auto-sync is enabled, push the result to Twenty CRM."""
    from ..config import settings
    if not settings.twenty_crm_auto_sync or not settings.twenty_crm_url or not settings.twenty_crm_api_key:
        return
    if scrape_type not in ("person", "company", "extract_users"):
        return
    try:
        from .twenty_sync import TwentyCRMClient
        client = TwentyCRMClient(settings.twenty_crm_url, settings.twenty_crm_api_key)
        result = await client.sync_result(scrape_type, result_json)
        logger.info("Auto-synced %s to CRM: %s", scrape_type, result)
        await client.close()
    except Exception as e:
        logger.warning("Auto-sync to CRM failed: %s", e)


async def run_extract_users(
    pool: BrowserPool,
    job_id: str,
    session_entries: list[dict],
    params: dict,
) -> None:
    """Background task for extract-users with multi-session rotation."""
    async with async_session() as db:
        callback = WebSocketCallback(job_id, db)

        try:
            # Start all sessions and build the rotator
            rotator = SessionRotator()
            first_page = None

            for entry in session_entries:
                browser = await pool.get_browser(entry["id"], entry["file"])
                rotator.add(entry["id"], browser.page)
                if first_page is None:
                    first_page = browser.page

            scraper = ExtractUsersFromPostsScraper(
                first_page, callback, rotator=rotator
            )
            result = await scraper.scrape(
                params["company_url"],
                posts_limit=params.get("posts_limit", 10),
                scrape_profiles=params.get("scrape_profiles", False),
            )
            result_json = result.model_dump_json()

            # Store result
            db.add(ScrapeResult(
                job_id=job_id,
                scrape_type="extract_users",
                result_data=result_json,
            ))
            await db.execute(
                update(ScrapeJob)
                .where(ScrapeJob.id == job_id)
                .values(
                    status="completed",
                    progress_percent=100,
                    completed_at=datetime.now(timezone.utc),
                )
            )
            await db.commit()
            await callback.on_complete("extract_users", result)

            await _auto_sync_to_crm("extract_users", result_json)

        except Exception as e:
            logger.exception("Extract-users job %s failed", job_id)
            await callback.on_error(e)
            try:
                await db.execute(
                    update(ScrapeJob)
                    .where(ScrapeJob.id == job_id)
                    .values(status="failed", error_message=str(e))
                )
                await db.commit()
            except Exception:
                pass
