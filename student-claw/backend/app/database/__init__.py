"""
Student Claw — database package.

Re-exports the connection utilities and ORM models so the rest of the backend
can do clean imports:

    from app.database import session_scope, Student, Project
"""

from app.database.connection import (
    AsyncSessionLocal,
    DATABASE_URL,
    dispose_engine,
    engine,
    get_session,
    session_scope,
)
from app.database.init_db import create_all, drop_all, init_db
from app.database.models import (
    Base,
    ContentType,
    ContributionMetric,
    Deadline,
    DeadlineExtractedBy,
    LinkedVia,
    MemberRole,
    MessageLog,
    Project,
    ProjectLinkToken,
    ProjectStatus,
    Student,
    StudentProject,
    Task,
    TaskSource,
    TaskStatus,
)

__all__ = [
    # connection
    "engine",
    "AsyncSessionLocal",
    "DATABASE_URL",
    "get_session",
    "session_scope",
    "dispose_engine",
    # init
    "init_db",
    "create_all",
    "drop_all",
    # base + enums
    "Base",
    "ProjectStatus",
    "MemberRole",
    "LinkedVia",
    "TaskSource",
    "TaskStatus",
    "DeadlineExtractedBy",
    "ContentType",
    # models
    "Student",
    "Project",
    "StudentProject",
    "Task",
    "Deadline",
    "MessageLog",
    "ContributionMetric",
    "ProjectLinkToken",
]
