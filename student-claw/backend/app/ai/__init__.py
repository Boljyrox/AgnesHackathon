"""
Student Claw — AI / RAG subsystem (Module 3).

Public surface:

    from app.ai.agent import run_agent
    from app.ai.pipeline import vectorize_message, semantic_search, run_worker
    from app.ai.queue import enqueue_embed_job
    from app.ai import storage

Note: importing this package does not eagerly construct network clients; the
Agnes/Qdrant/MinIO clients are lazy singletons created on first use.
"""

from app.ai.config import collection_name

__all__ = ["collection_name"]
