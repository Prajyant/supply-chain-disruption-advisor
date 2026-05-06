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
    # Gemini AI (legacy, kept for backward compatibility)
    gemini_api_key: str | None = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or None
    gemini_model: str = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
    # Amazon Bedrock
    aws_access_key_id: str | None = os.getenv("AWS_ACCESS_KEY_ID") or None
    aws_secret_access_key: str | None = os.getenv("AWS_SECRET_ACCESS_KEY") or None
    aws_session_token: str | None = os.getenv("AWS_SESSION_TOKEN") or None
    aws_region: str = os.getenv("AWS_REGION", "us-east-1")
    bedrock_model_id: str = os.getenv("BEDROCK_MODEL_ID", "us.anthropic.claude-sonnet-4-20250514-v1:0")
    # AWS SES Email
    ses_sender_email: str = os.getenv("SES_SENDER_EMAIL", "")
    ses_region: str | None = os.getenv("SES_REGION") or None
    ses_alert_recipients: str = os.getenv("SES_ALERT_RECIPIENTS", "")
    # Role-based recipient lists (comma-separated emails)
    ses_recipients_operations: str = os.getenv("SES_RECIPIENTS_OPERATIONS", "")
    ses_recipients_finance: str = os.getenv("SES_RECIPIENTS_FINANCE", "")
    ses_recipients_analyst: str = os.getenv("SES_RECIPIENTS_ANALYST", "")
    ses_recipients_executive: str = os.getenv("SES_RECIPIENTS_EXECUTIVE", "")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
