import os

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str
    OPENAI_API_KEY: str

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()

# pydantic-ai / openai SDK read the API key from this env var. Setting it
# once here (after .env is loaded) means agent modules don't need their own
# import-time side effects.
os.environ.setdefault("OPENAI_API_KEY", settings.OPENAI_API_KEY)
