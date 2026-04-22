"""WebSocket-based ProgressCallback for real-time scrape progress."""

import json
import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import WebSocket
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from linkedin_scraper.callbacks import ProgressCallback

from .models import ScrapeJob

logger = logging.getLogger(__name__)

# Global registry: job_id -> list of connected WebSocket clients
active_connections: dict[str, list[WebSocket]] = {}


class WebSocketCallback(ProgressCallback):
    """Bridges the scraper's callback protocol to WebSocket clients and the DB."""

    def __init__(self, job_id: str, db: AsyncSession):
        self.job_id = job_id
        self.db = db

    async def on_start(self, scraper_type: str, url: str) -> None:
        await self._broadcast({"event": "start", "scraper_type": scraper_type, "url": url})
        await self._update_job(status="running", progress_percent=0, started_at=datetime.now(timezone.utc))

    async def on_progress(self, message: str, percent: int) -> None:
        await self._broadcast({"event": "progress", "message": message, "percent": percent})
        await self._update_job(progress_percent=percent, progress_message=message)

    async def on_complete(self, scraper_type: str, result: Any) -> None:
        await self._broadcast({"event": "complete", "scraper_type": scraper_type})
        await self._update_job(
            status="completed",
            progress_percent=100,
            completed_at=datetime.now(timezone.utc),
        )

    async def on_error(self, error: Exception) -> None:
        await self._broadcast({"event": "error", "message": str(error)})
        await self._update_job(status="failed", error_message=str(error))

    async def _broadcast(self, data: dict) -> None:
        """Send JSON message to all WebSocket clients watching this job."""
        clients = active_connections.get(self.job_id, [])
        dead: list[WebSocket] = []
        for ws in clients:
            try:
                await ws.send_json(data)
            except Exception:
                dead.append(ws)
        for ws in dead:
            clients.remove(ws)

    async def _update_job(self, **fields) -> None:
        """Persist progress to the scrape_jobs row."""
        try:
            await self.db.execute(
                update(ScrapeJob).where(ScrapeJob.id == self.job_id).values(**fields)
            )
            await self.db.commit()
        except Exception as e:
            logger.error("Failed to update job %s: %s", self.job_id, e)
