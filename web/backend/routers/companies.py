"""Companies monitoring + scrape orchestration endpoints."""

import asyncio
import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from typing import Optional

from ..config import settings
from ..services.twenty_crud import TwentyCRUD
from ..services import company_scrape_service
from ..ws_callback import WebSocketCallback, active_connections
from ..database import get_db, async_session

# In-memory cache for run status — avoids hitting CRM API on every poll
_run_cache: dict[str, dict] = {}

router = APIRouter()


def _clean_linkedin_url(url: str) -> str:
    """Strip /posts/, query params, and trailing slashes from LinkedIn URLs."""
    url = url.split("?")[0].rstrip("/")
    if "/posts" in url:
        url = url.split("/posts")[0]
    return url


def _extract_linkedin_url(company: dict) -> str:
    """Extract the LinkedIn URL string from a Twenty company record."""
    lu = company.get("linkedinUrl")
    if isinstance(lu, dict):
        return lu.get("primaryLinkUrl", "")
    return lu or ""


def _get_crud() -> TwentyCRUD:
    if not settings.twenty_crm_url or not settings.twenty_crm_api_key:
        raise HTTPException(status_code=400, detail="CRM not configured")
    return TwentyCRUD(settings.twenty_crm_url, settings.twenty_crm_api_key)


def _pool(request: Request):
    return request.app.state.browser_pool


# ── Schemas ───────────────────────────────────────────────────────

class AddCompanyRequest(BaseModel):
    linkedin_url: str
    name: Optional[str] = None


class StartScrapeRequest(BaseModel):
    session_ids: list[str]


# ── Company endpoints ─────────────────────────────────────────────

@router.get("/companies")
async def list_companies(search: str = ""):
    """List companies from Twenty CRM."""
    crud = _get_crud()
    try:
        companies = await crud.list_companies(search=search if search else None, limit=100)
        return {"companies": companies}
    finally:
        await crud.close()


@router.post("/companies", status_code=201)
async def add_company(body: AddCompanyRequest):
    """Add a company to monitor — creates in CRM if not exists."""
    crud = _get_crud()
    try:
        clean_url = _clean_linkedin_url(body.linkedin_url)

        # Check if already exists
        existing = await crud.find_company_by_linkedin_url(clean_url)
        if existing:
            return {"company": existing, "action": "existing"}

        # Derive name from URL if not provided
        url_parts = clean_url.rstrip("/").split("/")
        auto_name = url_parts[-1].replace("-", " ").title() if url_parts else "Company"

        data = {
            "name": body.name or auto_name,
            "linkedinUrl": {"primaryLinkLabel": "LinkedIn", "primaryLinkUrl": clean_url},
        }
        crm_id = await crud.create_company(data)
        if not crm_id:
            raise HTTPException(status_code=500, detail="Failed to create company in CRM")

        company = await crud.get_company(crm_id)
        return {"company": company, "action": "created"}
    finally:
        await crud.close()


@router.get("/companies/{company_id}")
async def get_company(company_id: str):
    """Get company details."""
    crud = _get_crud()
    try:
        company = await crud.get_company(company_id)
        if not company:
            raise HTTPException(status_code=404, detail="Company not found")
        return {"company": company}
    finally:
        await crud.close()


@router.delete("/companies/{company_id}", status_code=200)
async def delete_company(company_id: str):
    """Delete a company from CRM."""
    crud = _get_crud()
    try:
        success = await crud.delete_company(company_id)
        if not success:
            raise HTTPException(status_code=404, detail="Company not found")
        return {"deleted": True}
    finally:
        await crud.close()


@router.get("/companies/{company_id}/posts")
async def get_company_posts(company_id: str):
    """Get posts for a company."""
    crud = _get_crud()
    try:
        company = await crud.get_company(company_id)
        if not company:
            raise HTTPException(status_code=404, detail="Company not found")

        linkedin_url = _extract_linkedin_url(company)

        posts = await crud.list_posts_for_company(linkedin_url)
        return {"posts": posts}
    finally:
        await crud.close()


@router.get("/companies/{company_id}/users")
async def get_company_users(company_id: str):
    """Get discovered users for a company."""
    crud = _get_crud()
    try:
        company = await crud.get_company(company_id)
        if not company:
            raise HTTPException(status_code=404, detail="Company not found")

        linkedin_url = _extract_linkedin_url(company)

        users = await crud.list_users_for_company(linkedin_url)
        return {"users": users}
    finally:
        await crud.close()


@router.get("/companies/{company_id}/runs")
async def get_company_runs(company_id: str):
    """Get scrape run history for a company."""
    crud = _get_crud()
    try:
        company = await crud.get_company(company_id)
        if not company:
            raise HTTPException(status_code=404, detail="Company not found")

        linkedin_url = _extract_linkedin_url(company)

        runs = await crud.list_runs_for_company(linkedin_url)
        return {"runs": runs}
    finally:
        await crud.close()


# ── Scrape run endpoints ──────────────────────────────────────────

@router.post("/companies/{company_id}/scrape", status_code=201)
async def start_scrape(company_id: str, body: StartScrapeRequest, request: Request):
    """Start a scrape run for a company."""
    if not body.session_ids:
        raise HTTPException(status_code=400, detail="At least one session required")

    crud = _get_crud()
    pool = _pool(request)

    try:
        company = await crud.get_company(company_id)
        if not company:
            raise HTTPException(status_code=404, detail="Company not found")

        linkedin_url = _extract_linkedin_url(company)

        if not linkedin_url:
            raise HTTPException(status_code=400, detail="Company has no LinkedIn URL")

        # Resolve session files
        from ..services.session_service import get_session
        async with async_session() as db:
            session_entries = []
            for sid in body.session_ids:
                s = await get_session(db, sid)
                if s:
                    session_entries.append({"id": s.id, "file": s.session_file})

        if not session_entries:
            raise HTTPException(status_code=400, detail="No valid sessions found")

        # Create run in CRM
        company_name = company.get("name", "Company")
        run_name = f"{company_name} - {datetime.now().strftime('%b %d %H:%M')}"
        run_crm_id = await crud.create_scrape_run({
            "name": run_name,
            "companyLinkedinUrl": linkedin_url,
            "companyCrmId": company_id,
            "status": "pending",
            "phase": "company_info",
            "progressPercent": 0,
            "sessionIdsJson": json.dumps(body.session_ids),
        })

        if not run_crm_id:
            raise HTTPException(status_code=500, detail="Failed to create scrape run")

        # Launch background task
        # Create a fresh crud client for the background task
        bg_crud = TwentyCRUD(settings.twenty_crm_url, settings.twenty_crm_api_key)

        asyncio.create_task(
            company_scrape_service.run_company_scrape(
                pool=pool,
                crud=bg_crud,
                run_crm_id=run_crm_id,
                company_crm_id=company_id,
                company_url=linkedin_url,
                session_entries=session_entries,
            )
        )

        run = await crud.get_scrape_run(run_crm_id)
        return {"run": run}
    finally:
        await crud.close()


@router.post("/companies/{company_id}/scrape-profiles", status_code=201)
async def start_profile_scrape(company_id: str, body: StartScrapeRequest, request: Request):
    """Start a profile-only scrape — skips posts, goes straight to scraping unscraped profiles."""
    if not body.session_ids:
        raise HTTPException(status_code=400, detail="At least one session required")

    crud = _get_crud()
    pool = _pool(request)

    try:
        company = await crud.get_company(company_id)
        if not company:
            raise HTTPException(status_code=404, detail="Company not found")

        linkedin_url = _extract_linkedin_url(company)
        if not linkedin_url:
            raise HTTPException(status_code=400, detail="Company has no LinkedIn URL")

        from ..services.session_service import get_session
        async with async_session() as db:
            session_entries = []
            for sid in body.session_ids:
                s = await get_session(db, sid)
                if s:
                    session_entries.append({"id": s.id, "file": s.session_file})

        if not session_entries:
            raise HTTPException(status_code=400, detail="No valid sessions found")

        company_name = company.get("name", "Company")
        run_name = f"{company_name} - Profiles - {datetime.now().strftime('%b %d %H:%M')}"
        run_crm_id = await crud.create_scrape_run({
            "name": run_name,
            "companyLinkedinUrl": linkedin_url,
            "companyCrmId": company_id,
            "status": "pending",
            "phase": "scraping_profiles",
            "progressPercent": 0,
            "sessionIdsJson": json.dumps(body.session_ids),
            "resumeStateJson": json.dumps({"phase": "scraping_profiles"}),
        })

        if not run_crm_id:
            raise HTTPException(status_code=500, detail="Failed to create scrape run")

        bg_crud = TwentyCRUD(settings.twenty_crm_url, settings.twenty_crm_api_key)
        asyncio.create_task(
            company_scrape_service.run_company_scrape(
                pool=pool, crud=bg_crud, run_crm_id=run_crm_id,
                company_crm_id=company_id, company_url=linkedin_url,
                session_entries=session_entries,
            )
        )

        run = await crud.get_scrape_run(run_crm_id)
        return {"run": run}
    finally:
        await crud.close()


@router.post("/companies/{company_id}/scrape-companies", status_code=201)
async def start_company_scrape(company_id: str, body: StartScrapeRequest, request: Request):
    """Scrape full details for all companies linked to discovered users (that haven't been scraped yet)."""
    if not body.session_ids:
        raise HTTPException(status_code=400, detail="At least one session required")

    crud = _get_crud()
    pool = _pool(request)

    try:
        company = await crud.get_company(company_id)
        if not company:
            raise HTTPException(status_code=404, detail="Company not found")

        linkedin_url = _extract_linkedin_url(company)
        if not linkedin_url:
            raise HTTPException(status_code=400, detail="Company has no LinkedIn URL")

        from ..services.session_service import get_session
        async with async_session() as db:
            session_entries = []
            for sid in body.session_ids:
                s = await get_session(db, sid)
                if s:
                    session_entries.append({"id": s.id, "file": s.session_file})

        if not session_entries:
            raise HTTPException(status_code=400, detail="No valid sessions found")

        company_name = company.get("name", "Company")
        run_name = f"{company_name} - Companies - {datetime.now().strftime('%b %d %H:%M')}"
        run_crm_id = await crud.create_scrape_run({
            "name": run_name,
            "companyLinkedinUrl": linkedin_url,
            "companyCrmId": company_id,
            "status": "pending",
            "phase": "scraping_companies",
            "progressPercent": 0,
            "sessionIdsJson": json.dumps(body.session_ids),
            "resumeStateJson": json.dumps({"phase": "scraping_companies"}),
        })

        if not run_crm_id:
            raise HTTPException(status_code=500, detail="Failed to create scrape run")

        bg_crud = TwentyCRUD(settings.twenty_crm_url, settings.twenty_crm_api_key)
        asyncio.create_task(
            company_scrape_service.run_company_scrape(
                pool=pool, crud=bg_crud, run_crm_id=run_crm_id,
                company_crm_id=company_id, company_url=linkedin_url,
                session_entries=session_entries,
            )
        )

        run = await crud.get_scrape_run(run_crm_id)
        return {"run": run}
    finally:
        await crud.close()


@router.post("/scrape-runs/{run_id}/pause")
async def pause_scrape(run_id: str):
    """Pause a running scrape."""
    crud = _get_crud()
    try:
        run = await crud.get_scrape_run(run_id)
        if not run:
            raise HTTPException(status_code=404, detail="Run not found")
        if run.get("status") != "running":
            raise HTTPException(status_code=400, detail=f"Run is {run.get('status')}, not running")
        await crud.update_scrape_run(run_id, {"status": "paused"})
        return {"status": "paused"}
    finally:
        await crud.close()


@router.post("/scrape-runs/{run_id}/resume")
async def resume_scrape(run_id: str, body: StartScrapeRequest, request: Request):
    """Resume a paused scrape."""
    crud = _get_crud()
    pool = _pool(request)

    try:
        run = await crud.get_scrape_run(run_id)
        if not run:
            raise HTTPException(status_code=404, detail="Run not found")
        if run.get("status") != "paused":
            raise HTTPException(status_code=400, detail=f"Run is {run.get('status')}, not paused")

        # Resolve sessions
        from ..services.session_service import get_session
        async with async_session() as db:
            session_entries = []
            for sid in body.session_ids:
                s = await get_session(db, sid)
                if s:
                    session_entries.append({"id": s.id, "file": s.session_file})

        if not session_entries:
            raise HTTPException(status_code=400, detail="No valid sessions found")

        await crud.update_scrape_run(run_id, {"status": "running"})

        company_url = run.get("companyLinkedinUrl", "")
        company_crm_id = run.get("companyCrmId", "")

        bg_crud = TwentyCRUD(settings.twenty_crm_url, settings.twenty_crm_api_key)

        asyncio.create_task(
            company_scrape_service.run_company_scrape(
                pool=pool,
                crud=bg_crud,
                run_crm_id=run_id,
                company_crm_id=company_crm_id,
                company_url=company_url,
                session_entries=session_entries,
            )
        )

        return {"status": "resumed"}
    finally:
        await crud.close()


@router.get("/scrape-runs/{run_id}")
async def get_scrape_run(run_id: str):
    """Get scrape run status — served from cache to avoid CRM API calls."""
    cached = _run_cache.get(run_id)
    if cached:
        return {"run": cached}
    # Fallback to CRM if not in cache (first load or completed runs)
    crud = _get_crud()
    try:
        run = await crud.get_scrape_run(run_id)
        if not run:
            raise HTTPException(status_code=404, detail="Run not found")
        return {"run": run}
    finally:
        await crud.close()


@router.websocket("/scrape-runs/ws/{run_id}")
async def scrape_run_ws(websocket: WebSocket, run_id: str):
    """WebSocket for live scrape progress."""
    await websocket.accept()
    active_connections.setdefault(run_id, []).append(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        conns = active_connections.get(run_id, [])
        if websocket in conns:
            conns.remove(websocket)
        if not conns:
            active_connections.pop(run_id, None)
