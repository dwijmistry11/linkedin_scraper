"""History and export endpoints."""

import json

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy import func, select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..models import ScrapeJob, ScrapeResult
from ..schemas import HistoryListResponse, ScrapeJobResponse, ScrapeResultResponse
from ..services.export_service import result_to_csv, result_to_json

router = APIRouter()


@router.get("", response_model=HistoryListResponse)
@router.get("/", response_model=HistoryListResponse, include_in_schema=False)
async def list_history(
    type: str | None = None,
    status: str | None = None,
    search: str | None = None,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    query = select(ScrapeJob)
    count_query = select(func.count(ScrapeJob.id))

    if type:
        query = query.where(ScrapeJob.scrape_type == type)
        count_query = count_query.where(ScrapeJob.scrape_type == type)
    if status:
        query = query.where(ScrapeJob.status == status)
        count_query = count_query.where(ScrapeJob.status == status)
    if search:
        pattern = f"%{search}%"
        filt = ScrapeJob.input_url.ilike(pattern)
        query = query.where(filt)
        count_query = count_query.where(filt)

    total = (await db.execute(count_query)).scalar() or 0

    query = query.order_by(ScrapeJob.created_at.desc())
    query = query.offset((page - 1) * per_page).limit(per_page)
    rows = (await db.execute(query)).scalars().all()

    return HistoryListResponse(
        items=[ScrapeJobResponse.model_validate(r) for r in rows],
        total=total,
        page=page,
        per_page=per_page,
    )


@router.get("/{job_id}", response_model=ScrapeJobResponse)
async def get_history_detail(job_id: str, db: AsyncSession = Depends(get_db)):
    job = await db.get(ScrapeJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.delete("/{job_id}", status_code=204)
async def delete_history(job_id: str, db: AsyncSession = Depends(get_db)):
    job = await db.get(ScrapeJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    # Delete result first (FK)
    result = await db.execute(select(ScrapeResult).where(ScrapeResult.job_id == job_id))
    row = result.scalar_one_or_none()
    if row:
        await db.delete(row)
    await db.delete(job)
    await db.commit()


@router.get("/{job_id}/export")
async def export_result(
    job_id: str,
    format: str = Query("json", pattern="^(json|csv)$"),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(ScrapeResult).where(ScrapeResult.job_id == job_id))
    row = result.scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Result not found")

    if format == "csv":
        content = result_to_csv(row.scrape_type, row.result_data)
        return Response(
            content=content,
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="scrape_{job_id}.csv"'},
        )
    else:
        content = result_to_json(row.result_data)
        return Response(
            content=content,
            media_type="application/json",
            headers={"Content-Disposition": f'attachment; filename="scrape_{job_id}.json"'},
        )
