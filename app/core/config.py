import os

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str
    OPENAI_API_KEY: str
    LOGFIRE_API_KEY: str = ""
    # Comma-separated list of allowed CORS origins.
    # Defaults to localhost dev server; override in production via env var.
    ALLOWED_ORIGINS: str = "http://localhost:5173"

    model_config = {"env_file": ".env", "extra": "ignore"}

    @property
    def allowed_origins_list(self) -> list[str]:
        return [o.strip() for o in self.ALLOWED_ORIGINS.split(",") if o.strip()]


settings = Settings()

# pydantic-ai / openai SDK read the API key from this env var. Setting it
# once here (after .env is loaded) means agent modules don't need their own
# import-time side effects.
os.environ.setdefault("OPENAI_API_KEY", settings.OPENAI_API_KEY)

# Logfire reads LOGFIRE_TOKEN from the environment.
if settings.LOGFIRE_API_KEY:
    os.environ.setdefault("LOGFIRE_TOKEN", settings.LOGFIRE_API_KEY)
