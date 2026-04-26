from functools import lru_cache
import os
from dotenv import load_dotenv
from pydantic import BaseModel

load_dotenv()


class Settings(BaseModel):
    openai_api_key: str | None = os.getenv("OPENAI_API_KEY") or None
    openai_model: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    api_host: str = os.getenv("API_HOST", "0.0.0.0")
    api_port: int = int(os.getenv("API_PORT", "8000"))
    # Live email inbox credentials
    imap_host: str = os.getenv("IMAP_HOST", "imap.gmail.com")
    imap_port: int = int(os.getenv("IMAP_PORT", "993"))
    imap_user: str | None = os.getenv("GMAIL_USER") or None
    imap_pass: str | None = os.getenv("GMAIL_APP_PASSWORD") or None


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
