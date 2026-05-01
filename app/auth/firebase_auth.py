"""Firebase Authentication helpers for FastAPI."""
import logging
import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import requests
from fastapi import HTTPException, status

try:
    import firebase_admin
    from firebase_admin import auth as firebase_auth
    from firebase_admin import credentials
except ImportError:
    firebase_admin = None
    firebase_auth = None
    credentials = None

try:
    import jwt
except ImportError:
    from jose import jwt

from app.auth.rbac import Role

logger = logging.getLogger(__name__)
FIREBASE_CERTS_URL = "https://www.googleapis.com/robot/v1/metadata/x509/securetoken@system.gserviceaccount.com"


@lru_cache(maxsize=1)
def initialize_firebase() -> bool:
    """Initialize Firebase Admin SDK if configuration is available."""
    if firebase_admin is None:
        logger.info("Firebase Admin SDK is not installed.")
        return False

    if firebase_admin._apps:
        return True

    service_account_path = os.getenv("FIREBASE_SERVICE_ACCOUNT_KEY", "").strip()
    project_id = os.getenv("FIREBASE_PROJECT_ID", "").strip()

    try:
        if service_account_path:
            path = Path(service_account_path)
            if not path.exists():
                logger.warning("Firebase service account file not found: %s", service_account_path)
                return False
            if credentials is None:
                return False
            firebase_admin.initialize_app(credentials.Certificate(str(path)))
            return True

        if project_id:
            firebase_admin.initialize_app(options={"projectId": project_id})
            return True
    except Exception as exc:
        logger.warning("Firebase initialization failed: %s", exc)
        return False

    logger.info("Firebase backend auth is not configured yet.")
    return False


def verify_firebase_token(token: str) -> dict[str, Any] | None:
    """Verify a Firebase ID token and return an app user dict."""
    result = verify_firebase_token_with_error(token)
    return result.get("user")


def verify_firebase_token_with_error(token: str) -> dict[str, Any]:
    """Verify a Firebase ID token and include non-secret failure details."""
    project_id = os.getenv("FIREBASE_PROJECT_ID", "").strip()

    if not project_id:
        return {
            "user": None,
            "error": "FIREBASE_PROJECT_ID is not configured.",
        }

    admin_error: Exception | None = None
    decoded_token: dict[str, Any] | None = None

    if initialize_firebase():
        try:
            if firebase_auth is not None:
                decoded_token = firebase_auth.verify_id_token(token)
        except Exception as exc:
            admin_error = exc
            logger.warning("Firebase Admin token verification failed: %s", exc)

    if decoded_token is None:
        try:
            decoded_token = verify_token_with_public_certs(token, project_id)
        except Exception as exc:
            logger.warning("Firebase public cert token verification failed: %s", exc)
            return {
                "user": None,
                "error": str(exc),
                "error_type": exc.__class__.__name__,
                "admin_error": str(admin_error) if admin_error else None,
            }

    email = decoded_token.get("email", "")
    role = decoded_token.get("role") or Role.BUYER.value

    return {
        "user": {
            "id": decoded_token.get("uid") or decoded_token.get("sub", ""),
            "username": decoded_token.get("name") or email or decoded_token.get("sub", "firebase-user"),
            "email": email,
            "role": Role(role) if role in Role._value2member_map_ else Role.BUYER,
            "auth_provider": "firebase",
        },
        "error": None,
    }


@lru_cache(maxsize=1)
def get_firebase_public_certs() -> dict[str, str]:
    """Fetch Google's public certs used to verify Firebase ID tokens."""
    response = requests.get(FIREBASE_CERTS_URL, timeout=10)
    response.raise_for_status()
    return response.json()


def verify_token_with_public_certs(token: str, project_id: str) -> dict[str, Any]:
    """Verify a Firebase ID token without local Google credentials."""
    header = jwt.get_unverified_header(token)
    key_id = header.get("kid")
    certs = get_firebase_public_certs()
    cert = certs.get(key_id)

    if not cert:
        get_firebase_public_certs.cache_clear()
        cert = get_firebase_public_certs().get(key_id)

    if not cert:
        raise ValueError("Firebase token key ID was not found in Google's public certificates.")

    return jwt.decode(
        token,
        cert,
        algorithms=["RS256"],
        audience=project_id,
        issuer=f"https://securetoken.google.com/{project_id}",
    )


def require_firebase_configured() -> None:
    """Raise a friendly error when Firebase backend auth has not been configured."""
    if not initialize_firebase():
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Firebase backend auth is not configured. Set FIREBASE_PROJECT_ID or FIREBASE_SERVICE_ACCOUNT_KEY.",
        )


def get_firebase_auth_status() -> dict[str, Any]:
    """Return non-secret Firebase auth configuration status."""
    service_account_path = os.getenv("FIREBASE_SERVICE_ACCOUNT_KEY", "").strip()
    project_id = os.getenv("FIREBASE_PROJECT_ID", "").strip()

    return {
        "configured": bool(project_id),
        "admin_sdk_configured": initialize_firebase(),
        "public_cert_verifier_enabled": bool(project_id),
        "has_project_id": bool(project_id),
        "project_id": project_id or None,
        "has_service_account_key": bool(service_account_path),
        "service_account_key_exists": Path(service_account_path).exists() if service_account_path else False,
    }
