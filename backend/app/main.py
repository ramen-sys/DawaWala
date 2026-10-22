from fastapi import FastAPI

from app.core.config import settings

app = FastAPI(title="Dawawala")


@app.get("/health")
def health():
    return {"status": "ok", "database_configured": bool(settings.database_url)}
