"""Pydantic request/response schemas for the API."""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel


# ── Sessions ──────────────────────────────────────────────────────────

class CreateSessionRequest(BaseModel):
    name: str
    cookie_value: Optional[str] = None  # li_at cookie


class LoginCookieRequest(BaseModel):
    cookie_value: str


class LoginCredentialsRequest(BaseModel):
    email: str
    password: str


class SessionResponse(BaseModel):
    id: str
    name: str
    is_active: bool
    last_verified_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ── Scraping ──────────────────────────────────────────────────────────

class ScrapePersonRequest(BaseModel):
    session_id: str
    url: str


class ScrapeCompanyRequest(BaseModel):
    session_id: str
    url: str


class ScrapeJobRequest(BaseModel):
    session_id: str
    url: str


class ScrapeJobSearchRequest(BaseModel):
    session_id: str
    keywords: Optional[str] = None
    location: Optional[str] = None
    limit: int = 25


class ScrapeCompanyPostsRequest(BaseModel):
    session_id: str
    company_url: str
    limit: int = 10


class ScrapeJobResponse(BaseModel):
    id: str
    session_id: str
    scrape_type: str
    input_url: str
    status: str
    progress_percent: int
    progress_message: Optional[str] = None
    error_message: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class ScrapeResultResponse(BaseModel):
    id: str
    job_id: str
    scrape_type: str
    result_data: Any  # parsed JSON
    created_at: datetime

    model_config = {"from_attributes": True}


# ── History ───────────────────────────────────────────────────────────

class HistoryListResponse(BaseModel):
    items: list[ScrapeJobResponse]
    total: int
    page: int
    per_page: int


# ── Settings ──────────────────────────────────────────────────────────

class AppSettingsResponse(BaseModel):
    browser_headless: bool
    browser_slow_mo: int
    max_concurrent_sessions: int


class UpdateSettingsRequest(BaseModel):
    browser_headless: Optional[bool] = None
    browser_slow_mo: Optional[int] = None
    max_concurrent_sessions: Optional[int] = None


class HealthResponse(BaseModel):
    status: str
    version: str
    active_browsers: int
