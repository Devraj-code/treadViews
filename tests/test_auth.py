"""Auth flow integration tests."""


def test_register_and_login(client):
    r = client.post(
        "/api/v1/auth/register",
        json={"email": "a@b.com", "password": "Password@123", "full_name": "A B"},
    )
    assert r.status_code == 201
    assert r.json()["email"] == "a@b.com"
    assert r.json()["role"] == "user"

    r2 = client.post("/api/v1/auth/login/json", json={"email": "a@b.com", "password": "Password@123"})
    assert r2.status_code == 200
    body = r2.json()
    assert body["access_token"] and body["refresh_token"]


def test_duplicate_registration_conflicts(client):
    payload = {"email": "dup@b.com", "password": "Password@123"}
    assert client.post("/api/v1/auth/register", json=payload).status_code == 201
    assert client.post("/api/v1/auth/register", json=payload).status_code == 409


def test_login_wrong_password(client):
    client.post("/api/v1/auth/register", json={"email": "c@b.com", "password": "Password@123"})
    r = client.post("/api/v1/auth/login/json", json={"email": "c@b.com", "password": "wrong"})
    assert r.status_code == 401


def test_refresh_token(client):
    client.post("/api/v1/auth/register", json={"email": "d@b.com", "password": "Password@123"})
    tokens = client.post("/api/v1/auth/login/json", json={"email": "d@b.com", "password": "Password@123"}).json()
    r = client.post("/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert r.status_code == 200
    assert r.json()["access_token"]


def test_me_requires_auth(client, auth_headers):
    assert client.get("/api/v1/auth/me").status_code == 401
    r = client.get("/api/v1/auth/me", headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["email"] == "tester@example.com"


def test_forgot_password_no_enumeration(client):
    r = client.post("/api/v1/auth/forgot-password", json={"email": "nobody@nowhere.com"})
    assert r.status_code == 200
