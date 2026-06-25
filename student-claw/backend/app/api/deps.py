"""
FastAPI dependencies: DB session, current student, and tenant guards.

Tenant isolation (blueprint §2.1, §8.1): every project-scoped route resolves the
caller's membership before touching project data, raising a structured 403/404
so cross-project access is impossible even with a forged project id.
"""

from __future__ import annotations

import uuid
from typing import Optional

import jwt
from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decode_access_token
from app.database.connection import get_session
from app.database.models import Project, Student, StudentProject


async def db_session() -> AsyncSession:  # pragma: no cover - thin wrapper
    async for session in get_session():
        yield session


async def get_current_student(
    authorization: Optional[str] = Header(default=None),
    session: AsyncSession = Depends(db_session),
) -> Student:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing bearer token.")
    token = authorization.split(" ", 1)[1].strip()

    try:
        payload = decode_access_token(token)
    except jwt.ExpiredSignatureError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token expired.")
    except jwt.InvalidTokenError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid token.")

    student = await session.get(Student, uuid.UUID(payload["sub"]))
    if student is None or not student.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Account not found or disabled.")
    return student


async def resolve_project(
    project_id: str, session: AsyncSession
) -> Project:
    try:
        pid = uuid.UUID(project_id)
    except ValueError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Project not found.")
    project = await session.get(Project, pid)
    if project is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Project not found.")
    return project


async def require_membership(
    project: Project, student: Student, session: AsyncSession
) -> StudentProject:
    membership = await session.scalar(
        select(StudentProject).where(
            StudentProject.project_id == project.id,
            StudentProject.student_id == student.id,
        )
    )
    if membership is None:
        # 404 (not 403) so we never reveal that a project exists to non-members.
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Project not found.")
    return membership


async def require_lead(
    project: Project, student: Student, session: AsyncSession
) -> StudentProject:
    membership = await require_membership(project, student, session)
    if membership.role.value != "lead":
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "This action requires the project lead role."
        )
    return membership
