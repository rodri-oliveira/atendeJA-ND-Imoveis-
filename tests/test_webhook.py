from fastapi.testclient import TestClient
from app.main import app
from app.core.config import settings


def test_webhook_verify_ok(monkeypatch):
    # Arrange
    token = "testtoken"
    old = settings.WA_VERIFY_TOKEN
    settings.WA_VERIFY_TOKEN = token
    client = TestClient(app)

    try:
        # Act
        resp = client.get(
            "/webhook",
            params={
                "hub.mode": "subscribe",
                "hub.challenge": "123",
                "hub.verify_token": token,
            },
        )
    finally:
        settings.WA_VERIFY_TOKEN = old

    # Assert
    assert resp.status_code == 200
    assert resp.text == "123"


def test_webhook_verify_forbidden(monkeypatch):
    # Arrange
    token = "right"
    old = settings.WA_VERIFY_TOKEN
    settings.WA_VERIFY_TOKEN = token
    client = TestClient(app)

    try:
        # Act
        resp = client.get(
            "/webhook",
            params={
                "hub.mode": "subscribe",
                "hub.challenge": "123",
                "hub.verify_token": "wrong",
            },
        )
    finally:
        settings.WA_VERIFY_TOKEN = old

    # Assert
    assert resp.status_code == 403


def test_webhook_post_enqueues_buffer(monkeypatch):
    # Arrange
    client = TestClient(app)

    calls = []

    class DummyTask:
        def delay(self, *args, **kwargs):
            calls.append((args, kwargs))

    # monkeypatch the Celery task object
    from app.api.routes import webhook as webhook_module

    monkeypatch.setattr(webhook_module, "buffer_incoming_message", DummyTask())

    # make tenant resolution deterministic for the test
    monkeypatch.setattr(webhook_module, "_resolve_tenant_from_phone_number_id", lambda db, pnid: type("T", (), {"id": 99})())

    payload = {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "metadata": {"phone_number_id": "12345"},
                            "contacts": [{"wa_id": "5561999999999"}],
                            "messages": [
                                {
                                    "from": "5561999999999",
                                    "type": "text",
                                    "text": {"body": "Ola"},
                                }
                            ],
                        }
                    }
                ]
            }
        ]
    }

    # Act
    resp = client.post("/webhook", json=payload)

    # Assert
    assert resp.status_code == 200
    assert resp.json().get("received") is True
    # ensure the task was enqueued with expected args
    assert calls, "buffer_incoming_message.delay was not called"
    args, kwargs = calls[0]
    assert args[0] == 99
    assert args[1] == "5561999999999"
    assert args[2] == "Ola"
    assert isinstance(args[3], dict)
