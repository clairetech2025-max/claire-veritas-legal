import time

import pytest

import license_manager as lm


@pytest.fixture
def state(tmp_path, monkeypatch):
    monkeypatch.setattr(lm, "STATE_DIR", tmp_path)
    monkeypatch.setattr(lm, "LICENSE_FILE", tmp_path / "license.json")
    monkeypatch.setattr(lm, "INSTALL_FILE", tmp_path / "install.json")
    monkeypatch.delenv("CLAIRE_LICENSE_SECRET", raising=False)
    return tmp_path


def _issued_token(**overrides):
    """Build a token the way the issuer would, signed with CLAIRE_LICENSE_SECRET."""
    now = int(time.time())
    payload = {
        "app": lm.APP_NAME,
        "license_type": "paid",
        "provider": "manual",
        "activation_id": "paid-test",
        "first_run_ts": now,
        "issued_ts": now,
        "expires_ts": now + 3600,
        "install_fingerprint": lm.get_install_fingerprint(),
        "subject": "firm",
        "grants": ["read", "chat"],
        "license_token": "",
        "license_signature": "",
    }
    payload.update(overrides)
    payload["license_signature"] = lm._sign(payload)
    return lm._encode_token(payload)


def _forged_token(**overrides):
    payload = {
        "app": lm.APP_NAME,
        "provider": "manual",
        "expires_ts": int(time.time()) + 10 * 365 * 86400,
        "install_fingerprint": lm.get_install_fingerprint(),
        "grants": ["read", "ingest", "chat", "admin"],
        "license_signature": "0" * 64,
        "license_token": "",
    }
    payload.update(overrides)
    return lm._encode_token(payload)


def test_activation_refused_without_issuer_secret(state):
    with pytest.raises(ValueError, match="not configured"):
        lm.activate_license(_forged_token())


def test_forged_token_is_rejected(state, monkeypatch):
    monkeypatch.setenv("CLAIRE_LICENSE_SECRET", "issuer-secret")
    with pytest.raises(ValueError, match="signature"):
        lm.activate_license(_forged_token())
    assert not lm.LICENSE_FILE.exists()


def test_token_signed_with_other_secret_is_rejected(state, monkeypatch):
    monkeypatch.setenv("CLAIRE_LICENSE_SECRET", "attacker-secret")
    token = _issued_token()
    monkeypatch.setenv("CLAIRE_LICENSE_SECRET", "issuer-secret")
    with pytest.raises(ValueError, match="signature"):
        lm.activate_license(token)


def test_genuine_token_activates_and_verifies(state, monkeypatch):
    monkeypatch.setenv("CLAIRE_LICENSE_SECRET", "issuer-secret")
    record = lm.activate_license(_issued_token(), provider="ignored")
    assert record["provider"] == "manual"
    status = lm.verify_license(lm.load_license())
    assert status.licensed and not status.expired


def test_token_for_other_install_is_rejected(state, monkeypatch):
    monkeypatch.setenv("CLAIRE_LICENSE_SECRET", "issuer-secret")
    with pytest.raises(ValueError, match="installation"):
        lm.activate_license(_issued_token(install_fingerprint="someone-else"))
    with pytest.raises(ValueError, match="installation"):
        lm.activate_license(_issued_token(install_fingerprint=""))


def test_expired_token_is_rejected(state, monkeypatch):
    monkeypatch.setenv("CLAIRE_LICENSE_SECRET", "issuer-secret")
    with pytest.raises(ValueError, match="expired"):
        lm.activate_license(_issued_token(expires_ts=int(time.time()) - 1))


def test_expired_evaluation_is_not_renewed(state, monkeypatch):
    first = lm.issue_evaluation_license()
    later = first["expires_ts"] + 10
    monkeypatch.setattr(lm.time, "time", lambda: later)
    kept = lm.ensure_license()
    assert kept["activation_id"] == first["activation_id"]
    assert lm.verify_license(kept).expired


def test_tampered_evaluation_is_replaced(state):
    first = lm.issue_evaluation_license()
    tampered = dict(first, expires_ts=first["expires_ts"] + 10 ** 8)
    lm.save_license(tampered)
    replaced = lm.ensure_license()
    assert replaced["activation_id"] != first["activation_id"]
    assert replaced["expires_ts"] == pytest.approx(time.time() + lm.EVALUATION_WINDOW_SECONDS, abs=60)
