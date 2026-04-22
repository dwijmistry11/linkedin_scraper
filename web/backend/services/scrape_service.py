"""Orchestrates scraping operations as background tasks."""

import json
import logging
from datetime import datetime, timezone

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from linkedin_scraper import (
    CompanyPostsScraper,
    CompanyScraper,
    JobScraper,
    JobSearchScraper,
    PersonScraper,
)

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

            except Exception as e:
                logger.exception("Scrape job %s failed", job_id)
                await callback.on_error(e)
                # Ensure failure is persisted even if callback DB write failed
                try:
                    await db.execute(
                        update(ScrapeJob)
                        .where(ScrapeJob.id == job_id)
                        .values(status="failed", error_message=str(e))
                    )
                    await db.commit()
                except Exception:
                    pass
