"""Scraping endpoints and WebSocket progress."""

import asyncio
import json

from fastapi import APIRouter, Depends, HTTPException, Request, WebSocket, WebSocketDisconnect
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..models import ScrapeJob, ScrapeResult
from ..schemas import (
    ExtractUsersRequest,
    ScrapeCompanyPostsRequest,
    ScrapeCompanyRequest,
    ScrapeJobRequest,
    ScrapeJobResponse,
    ScrapeJobSearchRequest,
    ScrapePersonRequest,
    ScrapeResultResponse,
)
from ..services import scrape_service
from ..services.session_service import get_session
from ..ws_callback import active_connections

router = APIRouter()


def _pool(request: Request):
    return request.app.state.browser_pool


async def _start_job(
    request: Request,
    db: AsyncSession,
    session_id: str,
    scrape_type: str,
    input_url: str,
    params: dict,
) -> ScrapeJob:
    """Create a scrape_jobs row and launch the background task."""
    session = await get_session(db, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    job = ScrapeJob(
        session_id=session_id,
        scrape_type=scrape_type,
        input_url=input_url,
        status="pending",
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)

    pool = _pool(request)
    asyncio.create_task(
        scrape_service.run_scrape(
            pool=pool,
            job_id=job.id,
            session_id=session_id,
            session_file=session.session_file,
            scrape_type=scrape_type,
            params=params,
        )
    )
    return job


@router.post("/person", response_model=ScrapeJobResponse, status_code=201)
async def scrape_person(
    body: ScrapePersonRequest, request: Request, db: AsyncSession = Depends(get_db)
):
    return await _start_job(request, db, body.session_id, "person", body.url, {"url": body.url})


@router.post("/company", response_model=ScrapeJobResponse, status_code=201)
async def scrape_company(
    body: ScrapeCompanyRequest, request: Request, db: AsyncSession = Depends(get_db)
):
    return await _start_job(request, db, body.session_id, "company", body.url, {"url": body.url})


@router.post("/job", response_model=ScrapeJobResponse, status_code=201)
async def scrape_job(
    body: ScrapeJobRequest, request: Request, db: AsyncSession = Depends(get_db)
):
    return await _start_job(request, db, body.session_id, "job", body.url, {"url": body.url})


@router.post("/job-search", response_model=ScrapeJobResponse, status_code=201)
async def scrape_job_search(
    body: ScrapeJobSearchRequest, request: Request, db: AsyncSession = Depends(get_db)
):
    input_url = json.dumps({"keywords": body.keywords, "location": body.location, "limit": body.limit})
    return await _start_job(
        request, db, body.session_id, "job_search", input_url,
        {"keywords": body.keywords, "location": body.location, "limit": body.limit},
    )


@router.post("/company-posts", response_model=ScrapeJobResponse, status_code=201)
async def scrape_company_posts(
    body: ScrapeCompanyPostsRequest, request: Request, db: AsyncSession = Depends(get_db)
):
    return await _start_job(
        request, db, body.session_id, "company_posts", body.company_url,
        {"company_url": body.company_url, "limit": body.limit},
    )


@router.post("/extract-users", response_model=ScrapeJobResponse, status_code=201)
async def extract_users(
    body: ExtractUsersRequest, request: Request, db: AsyncSession = Depends(get_db)
):
    if not body.session_ids:
        raise HTTPException(status_code=400, detail="At least one session_id is required")

    primary_session_id = body.session_ids[0]
    session = await get_session(db, primary_session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Primary session not found")

    # Resolve all session files for the rotator
    session_entries: list[dict] = []
    for sid in body.session_ids:
        s = await get_session(db, sid)
        if s:
            session_entries.append({"id": s.id, "file": s.session_file})

    job = ScrapeJob(
        session_id=primary_session_id,
        scrape_type="extract_users",
        input_url=body.company_url,
        status="pending",
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)

    pool = _pool(request)
    asyncio.create_task(
        scrape_service.run_extract_users(
            pool=pool,
            job_id=job.id,
            session_entries=session_entries,
            params={
                "company_url": body.company_url,
                "posts_limit": body.posts_limit,
                "scrape_profiles": body.scrape_profiles,
            },
        )
    )
    return job


@router.get("/{job_id}", response_model=ScrapeJobResponse)
async def get_scrape_job(job_id: str, db: AsyncSession = Depends(get_db)):
    job = await db.get(ScrapeJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.get("/{job_id}/result", response_model=ScrapeResultResponse)
async def get_scrape_result(job_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(ScrapeResult).where(ScrapeResult.job_id == job_id))
    row = result.scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Result not found")
    # Parse JSON string for the response
    return ScrapeResultResponse(
        id=row.id,
        job_id=row.job_id,
        scrape_type=row.scrape_type,
        result_data=json.loads(row.result_data),
        created_at=row.created_at,
    )


@router.websocket("/ws/{job_id}")
async def scrape_progress_ws(websocket: WebSocket, job_id: str):
    await websocket.accept()
    active_connections.setdefault(job_id, []).append(websocket)
    try:
        while True:
            await websocket.receive_text()  # keep-alive / ping
    except WebSocketDisconnect:
        pass
    finally:
        conns = active_connections.get(job_id, [])
        if websocket in conns:
            conns.remove(websocket)
        if not conns:
            active_connections.pop(job_id, None)
