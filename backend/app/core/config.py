from functools import lru_cache
from pathlib import Path

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Ensure this points directly to the directory containing .env (backend/)
# If config.py is at backend/app/config.py, use .parents[1]
# If config.py is at backend/app/core/config.py, use .parents[2]
BACKEND_DIR = Path(__file__).resolve().parents[2]
ENV_FILE = BACKEND_DIR / ".env"

class Settings(BaseSettings):
    """Runtime configuration. Values come from environment variables or backend/.env."""

    model_config = SettingsConfigDict(
        env_file=ENV_FILE, 
        env_file_encoding="utf-8",
        extra="ignore"
    )

    APP_NAME: str = "Dawawala API"
    API_PREFIX: str = "/api/v1"

    # Let Pydantic auto-populate from .env (Do NOT use os.getenv!)
    DATABASE_URL: str
    JWT_SECRET_KEY: str = Field(validation_alias=AliasChoices("JWT_SECRET_KEY", "JWT_SECRET"))
    JWT_SECRET_KEY: str = "temporary_secret_key_change_in_production"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    CORS_ORIGINS: str = "http://localhost:5173"

    PASSWORD_MIN_LEN: int = 8
    MAX_FAILED_LOGINS: int = 5
    LOCKOUT_MIN: int = 15
    MAX_MEDS_PER_LIST: int = 30
    NAME_MIN_LEN: int = 2
    NAME_MAX_LEN: int = 100
    MAX_IMAGE_BYTES: int = 10 * 1024 * 1024
    MAX_IMAGES_PER_LIST: int = 5
    MATCH_HIGH: int = 90
    MATCH_LOW: int = 70

    # Must match knowledge_base/data/kb_meta.json (scripts.import_kb_rules checks this).

    # FR-9: drug classes whose members count as a possible therapeutic duplication.
    # This is the single source of truth; scripts.import_kb_rules refuses to import if
    # knowledge_base/data/drug_classes.csv disagrees with it.
    KB_VERSION: str = "1.0"
    KB_UPDATED_ON: str = "2026-10-22"
    DUPLICATION_RELEVANT_CLASSES: str = (
        "Analgesic / antipyretic,NSAID,Proton-pump inhibitor,H2-receptor antagonist,Antihistamine,"
        "Macrolide antibiotic,Penicillin antibiotic,Fluoroquinolone antibiotic,Cephalosporin antibiotic,"
        "Leukotriene receptor antagonist,Benzodiazepine,Antidiarrhoeal,Mucolytic,"
        "Anticoagulant,Calcium channel blocker,ACE inhibitor,Loop diuretic,Statin,"
        "Cholinesterase inhibitor,Antimuscarinic"
    )

    LOG_DIR: Path = BACKEND_DIR / "logs"
    AUTH_LOG_RETENTION_DAYS: int = 90

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @property
    def duplication_relevant_classes(self) -> set[str]:
        return {c.strip() for c in self.DUPLICATION_RELEVANT_CLASSES.split(",") if c.strip()}


@lru_cache
def get_settings() -> Settings:
    return Settings()

settings = get_settings()
