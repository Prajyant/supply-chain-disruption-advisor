"""Live IMAP email reader for supply chain disruption detection."""
from __future__ import annotations

import email
import imaplib
import logging
import re
from email.header import decode_header
from typing import Any

from app.core.config import get_settings

logger = logging.getLogger(__name__)


def _decode_mime_words(value: str) -> str:
    """Decode encoded email header words (e.g. =?UTF-8?B?...?=)."""
    parts = decode_header(value or "")
    result = []
    for raw, charset in parts:
        if isinstance(raw, bytes):
            result.append(raw.decode(charset or "utf-8", errors="replace"))
        else:
            result.append(str(raw))
    return " ".join(result).strip()


def _extract_plain_text(msg: email.message.Message) -> str:
    """Walk a MIME message and return the first plain-text body found."""
    if msg.is_multipart():
        for part in msg.walk():
            ct = part.get_content_type()
            cd = str(part.get("Content-Disposition", ""))
            if ct == "text/plain" and "attachment" not in cd:
                charset = part.get_content_charset() or "utf-8"
                try:
                    return part.get_payload(decode=True).decode(charset, errors="replace")
                except Exception:
                    pass
    else:
        charset = msg.get_content_charset() or "utf-8"
        try:
            return msg.get_payload(decode=True).decode(charset, errors="replace")
        except Exception:
            pass
    return ""


def _extract_sender_name(from_header: str) -> str:
    """Pull a human-readable company/person name from a From: header."""
    # Try 'Display Name <email@domain>' pattern
    match = re.match(r"^(.+?)\s*<", from_header)
    if match:
        name = match.group(1).strip().strip('"').strip("'")
        if name:
            return name
    # Fall back to just the email address domain
    email_match = re.search(r"[\w.+-]+@([\w.-]+)", from_header)
    if email_match:
        domain = email_match.group(1)
        # Strip TLD and return capitalised domain name
        return domain.split(".")[0].capitalize()
    return from_header[:50]


def fetch_live_emails(limit: int = 15) -> list[dict[str, Any]]:
    """
    Connect to Gmail via IMAP and fetch the most recent emails.

    Returns a list of event dicts compatible with the risk engine schema.
    Returns an empty list (with a log warning) if credentials are missing or
    the connection fails — so the app can gracefully fall back to the CSV.
    """
    settings = get_settings()

    if not settings.imap_user or not settings.imap_pass:
        logger.warning("IMAP credentials not set — skipping live email fetch.")
        return []

    try:
        mail = imaplib.IMAP4_SSL(settings.imap_host, settings.imap_port)
        mail.login(settings.imap_user, settings.imap_pass)
        mail.select("INBOX")

        # Fetch the IDs of the N most recent emails
        _, data = mail.search(None, "ALL")
        all_ids = data[0].split()
        recent_ids = all_ids[-limit:] if len(all_ids) > limit else all_ids
        recent_ids = list(reversed(recent_ids))  # newest first

        events: list[dict[str, Any]] = []
        for idx, mail_id in enumerate(recent_ids):
            try:
                _, msg_data = mail.fetch(mail_id, "(RFC822)")
                raw = msg_data[0][1]
                msg = email.message_from_bytes(raw)

                subject = _decode_mime_words(msg.get("Subject", "(No Subject)"))
                from_raw = _decode_mime_words(msg.get("From", ""))
                date_str = msg.get("Date", "")
                body = _extract_plain_text(msg)

                sender_name = _extract_sender_name(from_raw)
                text = f"{subject}. {body[:800]}"  # cap body to avoid huge tokens

                events.append({
                    "source": "live_email",
                    "reference_id": f"EMAIL-{idx+1}",
                    "supplier": sender_name,
                    "event_time": date_str,
                    "text": text,
                    "metadata": {
                        "subject": subject,
                        "from": from_raw,
                        "sender_name": sender_name,
                        "date": date_str,
                    },
                })
            except Exception as e:
                logger.warning(f"Could not parse email {mail_id}: {e}")

        mail.logout()
        logger.info(f"Fetched {len(events)} live emails from {settings.imap_user}")
        return events

    except imaplib.IMAP4.error as e:
        logger.error(f"IMAP authentication failed: {e}")
        return []
    except Exception as e:
        logger.error(f"Live email fetch failed: {e}")
        return []
