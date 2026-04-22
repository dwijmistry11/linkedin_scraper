"""CRUD and auth operations for LinkedIn sessions."""

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from linkedin_scraper import (
    BrowserManager,
    is_logged_in,
    login_with_cookie,
    login_with_credentials,
)

from ..browser_pool import BrowserPool
from ..config import settings
from ..models import LinkedInSession


async def list_sessions(db: AsyncSession) -> list[LinkedInSession]:
    result = await db.execute(select(LinkedInSession).order_by(LinkedInSession.created_at.desc()))
    return list(result.scalars().all())


async def get_session(db: AsyncSession, session_id: str) -> Optional[LinkedInSession]:
    return await db.get(LinkedInSession, session_id)


async def create_session(
    db: AsyncSession,
    name: str,
    cookie_value: Optional[str] = None,
    uploaded_file_content: Optional[bytes] = None,
) -> LinkedInSession:
    """Create a new session record. Optionally seed it with a cookie or uploaded JSON."""
    import uuid

    session_id = str(uuid.uuid4())
    session_filename = f"{session_id}.json"
    session_path = Path(settings.sessions_dir) / session_filename
    session_path.parent.mkdir(parents=True, exist_ok=True)

    if uploaded_file_content:
        session_path.write_bytes(uploaded_file_content)
    elif cookie_value:
        # Create a minimal Playwright storage-state JSON with the li_at cookie
        storage = {
            "cookies": [
                {
                    "name": "li_at",
                    "value": cookie_value,
                    "domain": ".linkedin.com",
                    "path": "/",
                    "httpOnly": True,
                    "secure": True,
                    "sameSite": "None",
                }
            ],
            "origins": [],
        }
        session_path.write_text(json.dumps(storage, indent=2))
    else:
        # Empty storage state — user will authenticate later
        session_path.write_text(json.dumps({"cookies": [], "origins": []}, indent=2))

    record = LinkedInSession(
        id=session_id,
        name=name,
        session_file=str(session_path),
    )
    db.add(record)
    await db.commit()
    await db.refresh(record)
    return record


async def verify_session(
    db: AsyncSession, pool: BrowserPool, session_id: str
) -> bool:
    """Start browser, load session, and check is_logged_in."""
    record = await get_session(db, session_id)
    if not record:
        raise ValueError("Session not found")

    authenticated = await pool.is_authenticated(session_id, record.session_file)
    record.is_active = authenticated
    if authenticated:
        record.last_verified_at = datetime.now(timezone.utc)
    await db.commit()
    return authenticated


async def login_session_cookie(
    db: AsyncSession, pool: BrowserPool, session_id: str, cookie_value: str
) -> LinkedInSession:
    """Authenticate a session using an li_at cookie value."""
    record = await get_session(db, session_id)
    if not record:
        raise ValueError("Session not found")

    browser = await pool.get_browser(session_id, record.session_file)
    await login_with_cookie(browser.page, cookie_value)

    # Persist the updated session to disk
    await browser.save_session(record.session_file)
    record.is_active = True
    record.last_verified_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(record)
    return record


async def login_session_credentials(
    db: AsyncSession, pool: BrowserPool, session_id: str, email: str, password: str
) -> LinkedInSession:
    """Authenticate a session using email/password."""
    record = await get_session(db, session_id)
    if not record:
        raise ValueError("Session not found")

    browser = await pool.get_browser(session_id, record.session_file)
    await login_with_credentials(browser.page, email=email, password=password)

    await browser.save_session(record.session_file)
    record.is_active = True
    record.last_verified_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(record)
    return record


async def delete_session(
    db: AsyncSession, pool: BrowserPool, session_id: str
) -> None:
    """Close browser, remove session file, delete DB record."""
    record = await get_session(db, session_id)
    if not record:
        raise ValueError("Session not found")

    await pool.close_browser(session_id)

    session_path = Path(record.session_file)
    if session_path.exists():
        session_path.unlink()

    await db.delete(record)
    await db.commit()
