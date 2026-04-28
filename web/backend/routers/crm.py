"""Twenty CRM integration endpoints."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..database import get_db
from ..models import ScrapeResult
from ..schemas import CRMSettingsResponse, CRMStatusResponse, CRMSyncResponse, UpdateCRMSettingsRequest
from ..services.twenty_sync import TwentyCRMClient

router = APIRouter()


def _get_client() -> TwentyCRMClient:
    if not settings.twenty_crm_url or not settings.twenty_crm_api_key:
        raise HTTPException(status_code=400, detail="CRM not configured. Set URL and API key first.")
    return TwentyCRMClient(settings.twenty_crm_url, settings.twenty_crm_api_key)


@router.get("/crm/settings", response_model=CRMSettingsResponse)
async def get_crm_settings():
    return CRMSettingsResponse(
        url=settings.twenty_crm_url,
        has_api_key=bool(settings.twenty_crm_api_key),
        auto_sync=settings.twenty_crm_auto_sync,
    )


@router.put("/crm/settings", response_model=CRMSettingsResponse)
async def update_crm_settings(body: UpdateCRMSettingsRequest):
    if body.url is not None:
        settings.twenty_crm_url = body.url.rstrip("/")
    if body.api_key is not None:
        settings.twenty_crm_api_key = body.api_key
    if body.auto_sync is not None:
        settings.twenty_crm_auto_sync = body.auto_sync
    return CRMSettingsResponse(
        url=settings.twenty_crm_url,
        has_api_key=bool(settings.twenty_crm_api_key),
        auto_sync=settings.twenty_crm_auto_sync,
    )


@router.get("/crm/status", response_model=CRMStatusResponse)
async def crm_status():
    if not settings.twenty_crm_url or not settings.twenty_crm_api_key:
        return CRMStatusResponse(connected=False, url=settings.twenty_crm_url or "")
    client = _get_client()
    connected = await client.check_connection()
    await client.close()
    return CRMStatusResponse(connected=connected, url=settings.twenty_crm_url)


@router.post("/crm/sync/{job_id}", response_model=CRMSyncResponse)
async def sync_to_crm(job_id: str, db: AsyncSession = Depends(get_db)):
    """Sync a single scrape result to Twenty CRM."""
    result = await db.execute(select(ScrapeResult).where(ScrapeResult.job_id == job_id))
    row = result.scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Result not found")

    client = _get_client()
    try:
        sync_result = await client.sync_result(row.scrape_type, row.result_data)

        # Mark as synced
        await db.execute(
            update(ScrapeResult)
            .where(ScrapeResult.id == row.id)
            .values(synced_to_crm=True, crm_sync_at=datetime.now(timezone.utc))
        )
        await db.commit()

        return CRMSyncResponse(success=True, detail=sync_result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Sync failed: {e}")
    finally:
        await client.close()


@router.post("/crm/sync-all", response_model=CRMSyncResponse)
async def sync_all_to_crm(db: AsyncSession = Depends(get_db)):
    """Sync all unsynced completed results to Twenty CRM."""
    results = await db.execute(
        select(ScrapeResult)
        .where(ScrapeResult.synced_to_crm == False)
        .where(ScrapeResult.scrape_type.in_(["person", "company", "extract_users"]))
    )
    rows = results.scalars().all()

    if not rows:
        return CRMSyncResponse(success=True, detail={"synced": 0, "message": "Nothing to sync"})

    client = _get_client()
    synced = 0
    failed = 0
    try:
        for row in rows:
            try:
                await client.sync_result(row.scrape_type, row.result_data)
                await db.execute(
                    update(ScrapeResult)
                    .where(ScrapeResult.id == row.id)
                    .values(synced_to_crm=True, crm_sync_at=datetime.now(timezone.utc))
                )
                synced += 1
            except Exception as e:
                failed += 1
        await db.commit()
        return CRMSyncResponse(success=True, detail={"synced": synced, "failed": failed})
    finally:
        await client.close()
