from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_NAME: str = "evermoments-api"
    APP_ENV: str = "development"
    DATABASE_URL: str = "sqlite:///./evermoments.db"
    FRONTEND_ORIGIN: str = "http://localhost:3000"
    CORS_ORIGINS: str = ""

    model_config = SettingsConfigDict(env_file="apps/api/.env", extra="ignore")

    @property
    def cors_origins(self) -> list[str]:
        if self.CORS_ORIGINS.strip():
            return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]
        if self.APP_ENV.lower() == "production":
            return []
        return [self.FRONTEND_ORIGIN]


settings = Settings()
