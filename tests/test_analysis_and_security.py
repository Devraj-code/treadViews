"""Tests for analysis/watchlist/schedule endpoints and security primitives."""
from app.core.security import (
    ACCESS_TOKEN,
    create_access_token,
    decode_token,
    decrypt_secret,
    encrypt_secret,
    hash_password,
    verify_password,
)


# ------------------------- security units ------------------------- #
def test_password_hash_roundtrip():
    h = hash_password("Secret@123")
    assert h != "Secret@123"
    assert verify_password("Secret@123", h)
    assert not verify_password("wrong", h)


def test_jwt_roundtrip():
    token = create_access_token("user-1", "user")
    payload = decode_token(token, expected_type=ACCESS_TOKEN)
    assert payload["sub"] == "user-1"
    assert payload["role"] == "user"
    assert decode_token(token, expected_type="refresh") is None


def test_credential_encryption_roundtrip():
    enc = encrypt_secret("tv-password")
    assert enc != "tv-password"
    assert decrypt_secret(enc) == "tv-password"


# ------------------------- API integration ------------------------- #
def test_watchlist_crud(client, auth_headers):
    r = client.post("/api/v1/watchlist", json={"symbol": "nse:nifty"}, headers=auth_headers)
    assert r.status_code == 201
    assert r.json()["symbol"] == "NSE:NIFTY"
    item_id = r.json()["id"]

    assert len(client.get("/api/v1/watchlist", headers=auth_headers).json()) == 1
    assert client.delete(f"/api/v1/watchlist/{item_id}", headers=auth_headers).status_code == 204


def test_analysis_run_creates_pending_job(client, auth_headers):
    r = client.post(
        "/api/v1/analysis/run",
        json={"symbol": "BINANCE:BTCUSDT", "timeframe": "4h", "indicators": ["RSI"]},
        headers=auth_headers,
    )
    assert r.status_code == 202
    body = r.json()
    assert body["symbol"] == "BINANCE:BTCUSDT"
    assert body["status"] == "pending"

    history = client.get("/api/v1/analysis/history", headers=auth_headers).json()
    assert len(history) == 1


def test_schedule_validation(client, auth_headers):
    bad = client.post(
        "/api/v1/schedule",
        json={"symbol": "NSE:NIFTY", "interval": "every_minute"},
        headers=auth_headers,
    )
    assert bad.status_code == 422

    good = client.post(
        "/api/v1/schedule",
        json={"symbol": "NSE:NIFTY", "interval": "hourly"},
        headers=auth_headers,
    )
    assert good.status_code == 201


def test_dashboard_summary(client, auth_headers):
    r = client.get("/api/v1/dashboard/summary", headers=auth_headers)
    assert r.status_code == 200
    assert "total_jobs" in r.json()


def test_admin_routes_forbidden_for_user(client, auth_headers):
    assert client.get("/api/v1/admin/users", headers=auth_headers).status_code == 403
