import hashlib
import hmac

from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.database import get_db
from app.main import app


class _Session:
    def add(self, _receipt):
        pass

    async def flush(self):
        pass


def _client() -> TestClient:
    async def override_db():
        yield _Session()

    app.dependency_overrides[get_db] = override_db
    return TestClient(app)


def test_webhook_fails_closed_when_secret_missing(monkeypatch):
    monkeypatch.setattr(settings, "RAZORPAY_WEBHOOK_SECRET", "")
    with _client() as client:
        response = client.post("/api/v1/webhooks/razorpay", content=b"{}")
    assert response.status_code == 503
    app.dependency_overrides.clear()


def test_webhook_rejects_invalid_signature(monkeypatch):
    monkeypatch.setattr(settings, "RAZORPAY_WEBHOOK_SECRET", "unit-secret")
    with _client() as client:
        response = client.post(
            "/api/v1/webhooks/razorpay", content=b"{}",
            headers={"x-razorpay-event-id": "evt_invalid", "x-razorpay-signature": "bad"},
        )
    assert response.status_code == 400
    app.dependency_overrides.clear()


def test_webhook_accepts_only_valid_raw_body_signature(monkeypatch):
    secret = "unit-secret"
    body = b'{"event":"payment.captured"}'
    signature = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    monkeypatch.setattr(settings, "RAZORPAY_WEBHOOK_SECRET", secret)
    with _client() as client:
        response = client.post(
            "/api/v1/webhooks/razorpay", content=body,
            headers={
                "content-type": "application/json",
                "x-razorpay-event-id": "evt_valid",
                "x-razorpay-event": "payment.captured",
                "x-razorpay-signature": signature,
            },
        )
    assert response.status_code == 200
    assert response.json()["status"] == "ACCEPTED"
    app.dependency_overrides.clear()
