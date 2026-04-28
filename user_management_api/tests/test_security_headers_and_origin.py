from app.core.config import settings


def test_security_headers_present_on_html_and_json(client):
    # HTML response
    r = client.get("/password/reset", params={"token": "x"})
    assert r.status_code == 200
    assert r.headers.get("Referrer-Policy") == "no-referrer"
    assert r.headers.get("X-Content-Type-Options") == "nosniff"
    assert r.headers.get("X-Frame-Options") == "DENY"
    assert "Content-Security-Policy" in r.headers

    # JSON response
    r2 = client.post("/password/forgot", json={"email": "nobody@test.local"})
    assert r2.status_code == 200
    assert r2.headers.get("Referrer-Policy") == "no-referrer"
    assert r2.headers.get("X-Content-Type-Options") == "nosniff"
    # CSP is intentionally skipped for JSON responses.
    assert "Content-Security-Policy" not in r2.headers


def test_html_form_posts_reject_wrong_origin(client):
    # Ensure a stable expected origin for this test.
    old = settings.public_base_url
    try:
        settings.public_base_url = "http://localhost:8000"

        r = client.post(
            "/password/reset-form",
            data={"token": "x", "password": "NewPass123!"},
            headers={"Origin": "http://evil.example"},
        )
        assert r.status_code == 403
        assert r.json()["detail"] == "Origin not allowed"

        r2 = client.post(
            "/invites/accept-form",
            data={"token": "x", "password": "NewPass123!", "full_name": "X"},
            headers={"Origin": "http://evil.example"},
        )
        assert r2.status_code == 403
        assert r2.json()["detail"] == "Origin not allowed"
    finally:
        settings.public_base_url = old
