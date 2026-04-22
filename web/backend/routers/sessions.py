"""Session management endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..schemas import (
    CreateSessionRequest,
    LoginCookieRequest,
    LoginCredentialsRequest,
    SessionResponse,
)
from ..services import session_service

router = APIRouter()


def _pool(request: Request):
    return request.app.state.browser_pool


@router.get("", response_model=list[SessionResponse])
@router.get("/", response_model=list[SessionResponse], include_in_schema=False)
async def list_sessions(db: AsyncSession = Depends(get_db)):
    return await session_service.list_sessions(db)


@router.get("/{session_id}", response_model=SessionResponse)
async def get_session(session_id: str, db: AsyncSession = Depends(get_db)):
    record = await session_service.get_session(db, session_id)
    if not record:
        raise HTTPException(status_code=404, detail="Session not found")
    return record


@router.post("", response_model=SessionResponse, status_code=201)
@router.post("/", response_model=SessionResponse, status_code=201, include_in_schema=False)
async def create_session(body: CreateSessionRequest, db: AsyncSession = Depends(get_db)):
    return await session_service.create_session(db, name=body.name, cookie_value=body.cookie_value)


@router.post("/upload", response_model=SessionResponse, status_code=201)
async def create_session_upload(
    name: str,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    content = await file.read()
    return await session_service.create_session(db, name=name, uploaded_file_content=content)


@router.post("/{session_id}/verify")
async def verify_session(
    session_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    try:
        authenticated = await session_service.verify_session(db, _pool(request), session_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Verification error: {e}")
    return {"authenticated": authenticated}


@router.post("/{session_id}/login-cookie", response_model=SessionResponse)
async def login_cookie(
    session_id: str,
    body: LoginCookieRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    try:
        return await session_service.login_session_cookie(
            db, _pool(request), session_id, body.cookie_value
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{session_id}/login-credentials", response_model=SessionResponse)
async def login_credentials(
    session_id: str,
    body: LoginCredentialsRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    try:
        return await session_service.login_session_credentials(
            db, _pool(request), session_id, body.email, body.password
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{session_id}", status_code=204)
async def delete_session(
    session_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    try:
        await session_service.delete_session(db, _pool(request), session_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
