"""The in-memory knowledge base used by the safety engine (FR-8 to FR-12).

Loading the knowledge base reads every rule table, so it is done once per process and
cached. The first analysis loads it through that request's database session; an admin can
reload it after `scripts.import_kb_rules` without restarting the API.
"""

from __future__ import annotations

import logging
import threading

from fastapi import status
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.engine import KBValidationError, KnowledgeBase, load_kb_from_db

logger = logging.getLogger("dawawala.kb")

_lock = threading.Lock()
_cached: KnowledgeBase | None = None


def _load(db: Session) -> KnowledgeBase:
    try:
        kb = load_kb_from_db(db)
    except KBValidationError as exc:
        # Never analyse with a partly valid rule set; the errors are for the maintainers' log only.
        logger.error("Knowledge base failed validation: %s", exc)
        raise AppError(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "knowledge_base_unavailable",
            "The medication knowledge base is temporarily unavailable. Please try again later.",
        ) from exc
    logger.info(
        "Loaded knowledge base %s (%d medications, %d interaction pairs, %d cascade rules)",
        kb.version, len(kb.medications), len(kb.interactions), len(kb.cascades),
    )
    return kb


def get_knowledge_base(db: Session) -> KnowledgeBase:
    """The cached knowledge base, loaded on first use."""
    global _cached
    if _cached is None:
        with _lock:
            if _cached is None:
                _cached = _load(db)
    return _cached


def reload_knowledge_base(db: Session) -> KnowledgeBase:
    """Re-read every rule (after an import). The old copy stays in use if the new one is invalid."""
    global _cached
    with _lock:
        _cached = _load(db)
    return _cached


def clear_cache() -> None:
    global _cached
    with _lock:
        _cached = None
