import asyncio
import contextlib
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.core.config import settings
from app.core.errors import register_exception_handlers
from app.core.logging import configure_logging
from app.db.session import SessionLocal, engine
from app.routers import auth, medication_lists, medications
from app.services.auth_event_service import purge_old_events

configure_logging()
logger = logging.getLogger("dawawala")

DISCLAIMER = "Decision support only. This is not medical advice. Discuss these results with your doctor or pharmacist."
PURGE_INTERVAL_SECONDS = 24 * 60 * 60


def _purge_auth_events() -> None:
    with SessionLocal() as db:
        removed = purge_old_events(db)
    logger.info("Purged %d auth events older than %d days", removed, settings.AUTH_LOG_RETENTION_DAYS)


async def _purge_auth_events_daily() -> None:
    """SEC-10 retention: delete auth events older than 90 days at startup and then once a day."""
    while True:
        try:
            await run_in_threadpool(_purge_auth_events)
        except Exception:  # a purge failure must never take the API down
            logger.exception("Auth-event purge failed")
        await asyncio.sleep(PURGE_INTERVAL_SECONDS)


@asynccontextmanager
async def lifespan(_: FastAPI):
    task = asyncio.create_task(_purge_auth_events_daily())
    yield
    task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await task


app = FastAPI(
    title=settings.APP_NAME,
    version="1.0.0",
    description=f"Dawawala - Prescription Interaction Checker API.\n\n**{DISCLAIMER}**",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

register_exception_handlers(app)

app.include_router(auth.router, prefix=settings.API_PREFIX)
app.include_router(medication_lists.router, prefix=settings.API_PREFIX)
app.include_router(medications.router, prefix=settings.API_PREFIX)


@app.get("/health", tags=["Health"])
def health():
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    return {"status": "ok", "database": "ok"}
