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
from .routers import crm, history, scrape, sessions, settings as settings_router

frontend_dist = Path(__file__).resolve().parent.parent / "frontend" / "dist"


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    Path(settings.sessions_dir).mkdir(parents=True, exist_ok=True)
    await init_db()
    app.state.browser_pool = BrowserPool(
        sessions_dir=Path(settings.sessions_dir),
        headless=settings.browser_headless,
        slow_mo=settings.browser_slow_mo,
        max_sessions=settings.max_concurrent_sessions,
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
app.include_router(scrape.router, prefix="/api/scrape", tags=["scrape"])
app.include_router(history.router, prefix="/api/history", tags=["history"])
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
