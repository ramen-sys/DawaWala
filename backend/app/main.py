from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.core.config import settings
from app.core.errors import register_exception_handlers
from app.core.logging import configure_logging
from app.db.session import engine
from app.routers import auth, medication_lists, medications

configure_logging()

DISCLAIMER = "Decision support only. This is not medical advice. Discuss these results with your doctor or pharmacist."

app = FastAPI(
    title=settings.APP_NAME,
    version="1.0.0",
    description=f"Dawawala - Prescription Interaction Checker API.\n\n**{DISCLAIMER}**",
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
