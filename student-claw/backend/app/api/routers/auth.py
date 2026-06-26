"""Authentication endpoints (blueprint §4.1 Phase 1, §6.2)."""

from __future__ import annotations

import uuid

import jwt
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import db_session
from app.api.schemas import LoginIn, RefreshIn, RegisterIn, TokenPair
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_refresh_token,
    hash_password,
    verify_password,
)
from app.database.models import Student, StudentProject

router = APIRouter(prefix="/auth", tags=["auth"])


async def _project_ids(session: AsyncSession, student_id: uuid.UUID) -> list[str]:
    rows = await session.scalars(
        select(StudentProject.project_id).where(StudentProject.student_id == student_id)
    )
    return [str(pid) for pid in rows.all()]


async def _issue_tokens(session: AsyncSession, student: Student) -> TokenPair:
    project_ids = await _project_ids(session, student.id)
    return TokenPair(
        access_token=create_access_token(
            student_id=str(student.id),
            username=student.username,
            telegram_verified=student.telegram_user_id is not None,
            project_ids=project_ids,
        ),
        refresh_token=create_refresh_token(student_id=str(student.id)),
    )


@router.post("/register", response_model=TokenPair, status_code=status.HTTP_201_CREATED)
async def register(body: RegisterIn, session: AsyncSession = Depends(db_session)) -> TokenPair:
    student = Student(
        display_name=body.display_name,
        username=body.username,
        password_hash=hash_password(body.password),
        telegram_username=(body.telegram_username or None),
    )
    session.add(student)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Username or Telegram handle already in use.")
    await session.refresh(student)
    return await _issue_tokens(session, student)


@router.post("/login", response_model=TokenPair)
async def login(body: LoginIn, session: AsyncSession = Depends(db_session)) -> TokenPair:
    student = await session.scalar(select(Student).where(Student.username == body.username))
    if student is None or not verify_password(body.password, student.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid username or password.")
    if not student.is_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Account disabled.")
    return await _issue_tokens(session, student)


@router.post("/refresh", response_model=TokenPair)
async def refresh(body: RefreshIn, session: AsyncSession = Depends(db_session)) -> TokenPair:
    try:
        payload = decode_refresh_token(body.refresh_token)
    except jwt.ExpiredSignatureError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Refresh token expired.")
    except jwt.InvalidTokenError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid refresh token.")

    student = await session.get(Student, uuid.UUID(payload["sub"]))
    if student is None or not student.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Account not found or disabled.")
    # Rotation: a fresh access + refresh pair is issued on every call.
    return await _issue_tokens(session, student)
