"""
Database initialization for Student Claw.

Responsibilities:
  * Ensure required PostgreSQL extensions exist (`pgcrypto` for
    gen_random_uuid()).
  * Create all tables / enum types defined in `models.py`.
  * Provide a `drop_all` helper for local development / test teardown.

This module is intended as a bootstrap convenience. For evolving a live
schema, generate Alembic migrations instead (the blueprint mandates migration
scripts for schema changes).

CLI usage (from `backend/`):

    python -m app.database.init_db            # create extensions + tables
    python -m app.database.init_db --drop     # DROP everything, then recreate
"""

from __future__ import annotations

import argparse
import asyncio
import logging

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.database.connection import engine
from app.database.models import Base

logger = logging.getLogger("student_claw.init_db")


async def ensure_extensions(bound_engine: AsyncEngine) -> None:
    """Install extensions the schema depends on. Idempotent."""
    async with bound_engine.begin() as conn:
        # gen_random_uuid() lives in pgcrypto on most distributions.
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS pgcrypto"))
    logger.info("Ensured PostgreSQL extensions (pgcrypto).")


async def create_all(bound_engine: AsyncEngine) -> None:
    """Create enum types and all tables. Idempotent (checkfirst=True)."""
    await ensure_extensions(bound_engine)
    async with bound_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Created all tables (%d).", len(Base.metadata.tables))


async def drop_all(bound_engine: AsyncEngine) -> None:
    """Drop all tables and enum types. Destructive — dev/test only."""
    async with bound_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    logger.warning("Dropped all tables.")


async def init_db(drop: bool = False) -> None:
    """Top-level entrypoint. Optionally drop before (re)creating."""
    if drop:
        await drop_all(engine)
    await create_all(engine)


async def _main(drop: bool) -> None:
    try:
        await init_db(drop=drop)
    finally:
        await engine.dispose()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
    )
    parser = argparse.ArgumentParser(description="Initialize the Student Claw database.")
    parser.add_argument(
        "--drop",
        action="store_true",
        help="Drop all tables before recreating (DESTRUCTIVE).",
    )
    args = parser.parse_args()

    if args.drop:
        confirm = input("This will DROP ALL TABLES. Type 'yes' to continue: ")
        if confirm.strip().lower() != "yes":
            print("Aborted.")
            raise SystemExit(1)

    asyncio.run(_main(drop=args.drop))
