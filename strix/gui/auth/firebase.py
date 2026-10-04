"""Firebase Admin SDK initialization and token verification for iqAudi360."""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

import firebase_admin
from firebase_admin import auth as firebase_auth, credentials, firestore

logger = logging.getLogger(__name__)

_firebase_app: firebase_admin.App | None = None
_firestore_client = None


def init_firebase_admin() -> firebase_admin.App | None:
    """Initialize Firebase Admin SDK.

    Credential resolution order:
      1. FIREBASE_SERVICE_ACCOUNT_JSON env var  (full JSON string — best for Render)
      2. FIREBASE_CREDENTIALS env var           (path to a JSON file)
      3. firebase_service_account.json next to this file
      4. iqaudi360-firebase-adminsdk.json in cwd
    """
    global _firebase_app
    if _firebase_app is not None:
        return _firebase_app

    try:
        cred = None

        # ── 1. JSON string in env var (Render / cloud) ──────────────────────
        json_str = os.environ.get("FIREBASE_SERVICE_ACCOUNT_JSON", "").strip()
        if json_str:
            try:
                service_account_info = json.loads(json_str)
                cred = credentials.Certificate(service_account_info)
                logger.info("Firebase: loaded credentials from FIREBASE_SERVICE_ACCOUNT_JSON env var")
            except (json.JSONDecodeError, ValueError) as exc:
                logger.warning("FIREBASE_SERVICE_ACCOUNT_JSON is set but invalid JSON: %s", exc)

        # ── 2. File path in env var ──────────────────────────────────────────
        if cred is None:
            env_path = os.environ.get("FIREBASE_CREDENTIALS", "")
            if env_path and Path(env_path).is_file():
                cred = credentials.Certificate(env_path)
                logger.info("Firebase: loaded credentials from FIREBASE_CREDENTIALS path: %s", env_path)

        # ── 3. Render Secret Files & standard file locations ────────────────
        if cred is None:
            candidate_paths = [
                Path("/etc/secrets/firebase_service_account.json"),
                Path("/etc/secrets/serviceAccountKey.json"),
                Path("/etc/secrets/iqaudi360-firebase-adminsdk.json"),
                Path.cwd() / "firebase_service_account.json",
                Path.cwd() / "serviceAccountKey.json",
                Path.cwd() / "iqaudi360-firebase-adminsdk.json",
                Path(__file__).resolve().parent / "firebase_service_account.json",
            ]
            for candidate in candidate_paths:
                if candidate.is_file():
                    try:
                        cred = credentials.Certificate(str(candidate))
                        logger.info("Firebase: loaded credentials from file: %s", candidate)
                        break
                    except Exception as exc:
                        logger.warning("Failed loading credentials from %s: %s", candidate, exc)

        if cred is None:
            logger.warning(
                "Firebase Admin SDK: no credentials found. "
                "Set FIREBASE_SERVICE_ACCOUNT_JSON env var in Render. "
                "Demo login still works without Firebase."
            )
            return None

        _firebase_app = firebase_admin.initialize_app(cred, name="iqaudi360")
        logger.info("Firebase Admin SDK initialized successfully.")
        return _firebase_app

    except ValueError:
        # App already initialized
        try:
            _firebase_app = firebase_admin.get_app("iqaudi360")
            return _firebase_app
        except Exception as exc:
            logger.error("Failed to retrieve existing Firebase app: %s", exc)
            return None
    except Exception as exc:
        logger.error("Failed to initialize Firebase Admin SDK: %s", exc)
        return None


def get_firestore_client():
    """Return a Firestore client, initializing Firebase Admin if needed."""
    global _firestore_client
    if _firestore_client is not None:
        return _firestore_client

    app = init_firebase_admin()
    if app is None:
        return None

    try:
        _firestore_client = firestore.client(app=app)
        logger.info("Firestore client ready.")
        return _firestore_client
    except Exception as exc:
        logger.error("Failed to create Firestore client: %s", exc)
        return None


def verify_id_token(id_token: str) -> dict[str, Any] | None:
    """Verify Firebase ID Token. Returns decoded token dict or None."""
    app = init_firebase_admin()
    if not app:
        logger.error("Cannot verify token: Firebase Admin SDK not initialized")
        return None

    try:
        decoded = firebase_auth.verify_id_token(id_token, app=app, check_revoked=False)
        return decoded
    except Exception as exc:
        logger.warning("Firebase token verification failed: %s", exc)
        return None


def get_firebase_user(uid: str) -> Any:
    """Fetch Firebase user record by UID."""
    app = init_firebase_admin()
    if not app:
        return None
    try:
        return firebase_auth.get_user(uid, app=app)
    except Exception as exc:
        logger.debug("Firebase get_user failed for UID %s: %s", uid, exc)
        return None


def get_firebase_web_config() -> dict[str, str]:
    """Return public, client-safe Firebase Web SDK configuration.

    STRICT SECURITY RULE: Contains ONLY public web identifiers.
    Private keys and service account secrets are NEVER included here.
    """
    return {
        "apiKey": os.environ.get("FIREBASE_API_KEY", ""),
        "projectId": os.environ.get("FIREBASE_PROJECT_ID", "iqaudi360"),
        "authDomain": os.environ.get("FIREBASE_AUTH_DOMAIN", "iqaudi360.firebaseapp.com"),
        "storageBucket": os.environ.get("FIREBASE_STORAGE_BUCKET", "iqaudi360.appspot.com"),
        "messagingSenderId": os.environ.get("FIREBASE_MESSAGING_SENDER_ID", ""),
        "appId": os.environ.get("FIREBASE_APP_ID", ""),
    }
