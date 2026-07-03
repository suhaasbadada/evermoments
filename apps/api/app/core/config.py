from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_NAME: str = "evermoments-api"
    APP_ENV: str = "development"
    DATABASE_URL: str = "sqlite:///./evermoments.db"
    FRONTEND_ORIGIN: str = "http://localhost:3000"
    CORS_ORIGINS: str = ""

    # --- Cognee Memory Engine (Module 3) -------------------------------------
    # All optional with safe defaults: the API boots on MEMORY_BACKEND=local with
    # NO cognee keys set. The COGNEE_* fields are read only by the graph/blob
    # backends (Slice 7+) and are never touched while MEMORY_BACKEND=local.
    MEMORY_BACKEND: str = "local"          # local | graph | blob
    CONTRADICTION_WINDOW_MIN: int = 180    # double-dose look-back window (minutes)
    COGNEE_MODE: str = "local"             # local (embedded) | cloud (serve() to Cognee Cloud)
    COGNEE_CLOUD_URL: str = ""             # Cognee Cloud endpoint (required for COGNEE_MODE=cloud)
    COGNEE_API_KEY: str = ""               # Cognee Cloud key      (required for COGNEE_MODE=cloud)
    COGNEE_LLM_MODEL: str = "gpt-4o-mini"  # LLM cognee uses to extract (Slice 7+)
    COGNEE_LLM_API_KEY: str = ""           # LLM provider key           (Slice 7+)

    # --- Voice Ingest / STT (Module 2) --------------------------------------
    STT_BACKEND: str = "offline"  # offline | openai
    STT_MODEL: str = "gpt-4o-mini-transcribe"
    STT_TIMEOUT_SEC: float = 45.0
    OPENAI_API_KEY: str = ""
    OPENAI_TRANSCRIBE_URL: str = "https://api.openai.com/v1/audio/transcriptions"

    model_config = SettingsConfigDict(env_file="apps/api/.env", extra="ignore")

    @property
    def cors_origins(self) -> list[str]:
        if self.CORS_ORIGINS.strip():
            return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]
        if self.APP_ENV.lower() == "production":
            return []
        return [self.FRONTEND_ORIGIN]


settings = Settings()
