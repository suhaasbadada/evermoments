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

    # Optional query-answer synthesis via Groq for longer / multi-hop questions.
    # Safe by default: disabled unless explicitly enabled + key provided.
    MEMORY_USE_GROQ_SYNTHESIS: bool = False
    GROQ_API_KEY: str = ""
    GROQ_MODEL: str = "llama-3.1-8b-instant"

    # Optional on-disk persistence for the local in-memory backend. When set,
    # LocalStore snapshots events to this JSON file so data survives API reloads.
    MEMORY_LOCAL_PERSIST_PATH: str = ""

    model_config = SettingsConfigDict(env_file="apps/api/.env", extra="ignore")

    @property
    def cors_origins(self) -> list[str]:
        if self.CORS_ORIGINS.strip():
            return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]
        if self.APP_ENV.lower() == "production":
            return []

        # Local dev convenience: allow common loopback origins without forcing
        # users to keep FRONTEND_ORIGIN and browser URL perfectly aligned.
        defaults = [
            "http://localhost:3000",
            "http://127.0.0.1:3000",
            self.FRONTEND_ORIGIN,
        ]

        seen: set[str] = set()
        origins: list[str] = []
        for origin in defaults:
            value = origin.strip()
            if value and value not in seen:
                seen.add(value)
                origins.append(value)
        return origins


settings = Settings()
