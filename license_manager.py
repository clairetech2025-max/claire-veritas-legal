from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import platform
import secrets
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional


APP_NAME = "CLAIRE // VERITAS LEGAL"
EVALUATION_WINDOW_SECONDS = 72 * 60 * 60


def _default_state_dir() -> Path:
    base = os.environ.get("CLAIRE_STATE_DIR")
    if base:
        return Path(base).expanduser().resolve()
    return (Path(__file__).resolve().parent / ".claire_veritas").resolve()


STATE_DIR = _default_state_dir()
LICENSE_FILE = STATE_DIR / "license.json"
INSTALL_FILE = STATE_DIR / "install.json"


def _stable_machine_fingerprint() -> str:
    parts = [
        platform.node(),
        platform.system(),
        platform.release(),
        platform.version(),
        platform.machine(),
        os.environ.get("USERNAME", ""),
        os.environ.get("COMPUTERNAME", ""),
    ]
    raw = "|".join(parts).encode("utf-8", errors="ignore")
    return hashlib.sha256(raw).hexdigest()


def _install_salt() -> str:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    if INSTALL_FILE.exists():
        try:
            data = json.loads(INSTALL_FILE.read_text(encoding="utf-8"))
            salt = str(data.get("install_salt", "")).strip()
            if salt:
                return salt
        except Exception:
            pass
    salt = secrets.token_hex(16)
    INSTALL_FILE.write_text(
        json.dumps(
            {
                "app": APP_NAME,
                "install_salt": salt,
                "created_ts": int(time.time()),
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return salt


def get_install_fingerprint() -> str:
    digest = hashlib.sha256()
    digest.update(_stable_machine_fingerprint().encode("utf-8"))
    digest.update(_install_salt().encode("utf-8"))
    return digest.hexdigest()


def _license_secret() -> bytes:
    seed = os.environ.get("CLAIRE_LICENSE_SECRET")
    if seed:
        return seed.encode("utf-8")
    return get_install_fingerprint().encode("utf-8")


def _sign(payload: Dict[str, Any]) -> str:
    data = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hmac.new(_license_secret(), data, hashlib.sha256).hexdigest()


def _encode_token(payload: Dict[str, Any]) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _decode_token(token: str) -> Optional[Dict[str, Any]]:
    if not token:
        return None
    padding = "=" * (-len(token) % 4)
    try:
        raw = base64.urlsafe_b64decode(token + padding)
        return json.loads(raw.decode("utf-8"))
    except Exception:
        return None


@dataclass(frozen=True)
class LicenseStatus:
    licensed: bool
    expired: bool
    mode: str
    source: str
    first_run_ts: int
    expires_ts: int
    remaining_seconds: int
    install_fingerprint: str
    activation_id: str = ""
    provider: str = "evaluation"
    message: str = ""


def load_license() -> Dict[str, Any]:
    if not LICENSE_FILE.exists():
        return {}
    try:
        return json.loads(LICENSE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_license(payload: Dict[str, Any]) -> Dict[str, Any]:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    LICENSE_FILE.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload


def issue_evaluation_license() -> Dict[str, Any]:
    now = int(time.time())
    first_run_ts = now
    install_fingerprint = get_install_fingerprint()
    payload = {
        "app": APP_NAME,
        "license_type": "evaluation",
        "provider": "local",
        "activation_id": f"eval-{secrets.token_hex(8)}",
        "first_run_ts": first_run_ts,
        "issued_ts": now,
        "expires_ts": now + EVALUATION_WINDOW_SECONDS,
        "install_fingerprint": install_fingerprint,
        "subject": "local-evaluation",
        "grants": ["read", "ingest", "search", "timeline", "ocr", "chat"],
        "license_token": "",
        "license_signature": "",
    }
    payload["license_signature"] = _sign(payload)
    payload["license_token"] = _encode_token(payload)
    return save_license(payload)


def ensure_license() -> Dict[str, Any]:
    existing = load_license()
    if existing:
        status = verify_license(existing)
        if status.licensed or (not status.expired and str(existing.get("provider", "")).lower() not in {"", "local", "evaluation"}):
            return existing
    return issue_evaluation_license()


def verify_license(license_data: Optional[Dict[str, Any]] = None) -> LicenseStatus:
    payload = license_data or ensure_license()
    now = int(time.time())
    first_run_ts = int(payload.get("first_run_ts") or payload.get("issued_ts") or now)
    expires_ts = int(payload.get("expires_ts") or (first_run_ts + EVALUATION_WINDOW_SECONDS))
    install_fingerprint = str(payload.get("install_fingerprint") or get_install_fingerprint())
    expected_signature = payload.get("license_signature", "")
    unsigned = dict(payload)
    unsigned["license_signature"] = ""
    unsigned["license_token"] = ""
    computed_signature = _sign(unsigned)
    signature_ok = hmac.compare_digest(str(expected_signature), str(computed_signature))
    fp_ok = hmac.compare_digest(install_fingerprint, get_install_fingerprint())
    expired = now >= expires_ts
    licensed = bool(signature_ok and fp_ok and not expired)
    mode = "licensed" if licensed else "read_only" if expired else "evaluation"
    if licensed:
        message = "Evaluation license active."
    elif expired:
        message = "Evaluation period expired. Continue read-only."
    else:
        message = "Evaluation license present but not yet validated."
    return LicenseStatus(
        licensed=licensed,
        expired=expired,
        mode=mode,
        source=str(payload.get("provider", "evaluation")),
        first_run_ts=first_run_ts,
        expires_ts=expires_ts,
        remaining_seconds=max(0, expires_ts - now),
        install_fingerprint=install_fingerprint,
        activation_id=str(payload.get("activation_id", "")),
        provider=str(payload.get("provider", "evaluation")),
        message=message,
    )


def activate_license(token: str, provider: str = "manual") -> Dict[str, Any]:
    payload = _decode_token(token)
    if not payload:
        raise ValueError("Invalid license token.")
    payload = dict(payload)
    payload["provider"] = provider
    payload["license_token"] = ""
    payload["license_signature"] = _sign(payload)
    payload["license_token"] = token
    if str(payload.get("install_fingerprint", "")) not in {"", get_install_fingerprint()}:
        raise ValueError("License token does not match this installation.")
    return save_license(payload)


def license_payload() -> Dict[str, Any]:
    return load_license()


def license_summary() -> Dict[str, Any]:
    status = verify_license()
    return {
        "app": APP_NAME,
        "licensed": status.licensed,
        "expired": status.expired,
        "mode": status.mode,
        "remaining_seconds": status.remaining_seconds,
        "first_run_ts": status.first_run_ts,
        "expires_ts": status.expires_ts,
        "install_fingerprint": status.install_fingerprint,
        "activation_id": status.activation_id,
        "provider": status.provider,
        "message": status.message,
        "future_hooks": {
            "gumroad": True,
            "stripe": True,
            "manual_activation": True,
        },
    }
