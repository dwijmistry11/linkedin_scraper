"""FastAPI application entry point."""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from .browser_pool import BrowserPool
from .config import settings
from .database import init_db
from .routers import companies, crm, sessions, settings as settings_router

frontend_dist = Path(__file__).resolve().parent.parent / "frontend" / "dist"


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    Path(settings.sessions_dir).mkdir(parents=True, exist_ok=True)
    await init_db()
    # Load CRM settings from DB into memory
    from .database import async_session as _async_session
    from .models import AppConfig
    async with _async_session() as db:
        for key in ("crm_url", "crm_api_key", "crm_auto_sync"):
            row = await db.get(AppConfig, key)
            if row and row.value:
                if key == "crm_url":
                    settings.twenty_crm_url = row.value
                elif key == "crm_api_key":
                    settings.twenty_crm_api_key = row.value
                elif key == "crm_auto_sync":
                    settings.twenty_crm_auto_sync = row.value == "true"
    # Mark any "running" scrape runs as failed (can't be running if server just started)
    if settings.twenty_crm_url and settings.twenty_crm_api_key:
        try:
            from .services.twenty_crud import TwentyCRUD
            crud = TwentyCRUD(settings.twenty_crm_url, settings.twenty_crm_api_key)
            stale_runs = await crud._list("scrapeRuns", "scrapeRuns", {"filter": "status[eq]:running", "limit": "50"})
            for run in stale_runs:
                await crud.update_scrape_run(run["id"], {"status": "failed", "errorMessage": "Server restarted"})
            if stale_runs:
                import logging
                logging.getLogger(__name__).info("Marked %d stale runs as failed on startup", len(stale_runs))
            await crud.close()
        except Exception:
            pass

    app.state.browser_pool = BrowserPool(
        sessions_dir=Path(settings.sessions_dir),
        headless=settings.browser_headless,
        slow_mo=settings.browser_slow_mo,
        max_sessions=settings.max_concurrent_sessions,
        use_tor=settings.use_tor,
    )
    yield
    # Shutdown
    await app.state.browser_pool.close_all()


app = FastAPI(
    title="LinkedIn Scraper UI",
    version="1.0.0",
    lifespan=lifespan,
    redirect_slashes=False,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API routers
app.include_router(sessions.router, prefix="/api/sessions", tags=["sessions"])
app.include_router(companies.router, prefix="/api", tags=["companies"])
app.include_router(settings_router.router, prefix="/api", tags=["settings"])
app.include_router(crm.router, prefix="/api", tags=["crm"])

# Serve built React frontend in production.
# Uses a custom 404 handler so API routes take full priority:
# any 404 on a non-/api path serves index.html for client-side routing.
if frontend_dist.is_dir():
    app.mount("/assets", StaticFiles(directory=str(frontend_dist / "assets")), name="static")

    @app.exception_handler(StarletteHTTPException)
    async def spa_fallback(request: Request, exc: StarletteHTTPException):
        # API paths: return normal JSON error responses
        if request.url.path.startswith("/api"):
            return JSONResponse({"detail": exc.detail}, status_code=exc.status_code)
        # Non-API 404s: serve index.html so React Router handles client-side routes
        if exc.status_code == 404:
            return FileResponse(frontend_dist / "index.html")
        # Other HTTP errors on non-API paths
        return JSONResponse({"detail": exc.detail}, status_code=exc.status_code)
