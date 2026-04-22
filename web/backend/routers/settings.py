"""Settings and health check endpoints."""

from fastapi import APIRouter, Request

from linkedin_scraper import __version__

from ..config import settings
from ..schemas import AppSettingsResponse, HealthResponse, UpdateSettingsRequest

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health_check(request: Request):
    pool = request.app.state.browser_pool
    return HealthResponse(
        status="ok",
        version=__version__,
        active_browsers=pool.active_count,
    )


@router.get("/settings", response_model=AppSettingsResponse)
async def get_settings():
    return AppSettingsResponse(
        browser_headless=settings.browser_headless,
        browser_slow_mo=settings.browser_slow_mo,
        max_concurrent_sessions=settings.max_concurrent_sessions,
    )


@router.put("/settings", response_model=AppSettingsResponse)
async def update_settings(body: UpdateSettingsRequest):
    if body.browser_headless is not None:
        settings.browser_headless = body.browser_headless
    if body.browser_slow_mo is not None:
        settings.browser_slow_mo = body.browser_slow_mo
    if body.max_concurrent_sessions is not None:
        settings.max_concurrent_sessions = body.max_concurrent_sessions
    return AppSettingsResponse(
        browser_headless=settings.browser_headless,
        browser_slow_mo=settings.browser_slow_mo,
        max_concurrent_sessions=settings.max_concurrent_sessions,
    )
