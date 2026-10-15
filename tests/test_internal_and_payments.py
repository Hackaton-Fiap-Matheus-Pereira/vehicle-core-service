from datetime import UTC, datetime
from uuid import uuid4

from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy.exc import SQLAlchemyError


async def test_internal_status_requires_service_token(
    client: AsyncClient,
    vehicle_id: str,
) -> None:
    response = await client.put(
        f"/internal/v1/vehicles/{vehicle_id}/status",
        json={"status": "RESERVED"},
    )

    assert response.status_code == 403
    assert response.json()["error"]["message"] == "Token interno inválido"


async def test_internal_status_updates_canonical_vehicle_idempotently(
    client: AsyncClient,
    vehicle_id: str,
) -> None:
    headers = {"X-Service-Token": "test-service-token"}
    reserved = await client.put(
        f"/internal/v1/vehicles/{vehicle_id}/status",
        headers=headers,
        json={"status": "RESERVED"},
    )

    assert reserved.status_code == 200
    assert reserved.json()["status"] == "RESERVED"
    assert reserved.json()["source_version"] == 2

    repeated = await client.put(
        f"/internal/v1/vehicles/{vehicle_id}/status",
        headers=headers,
        json={"status": "RESERVED"},
    )
    assert repeated.status_code == 200
    assert repeated.json()["source_version"] == 2


async def test_internal_status_returns_not_found(client: AsyncClient) -> None:
    response = await client.put(
        "/internal/v1/vehicles/00000000-0000-0000-0000-000000000000/status",
        headers={"X-Service-Token": "test-service-token"},
        json={"status": "SOLD"},
    )

    assert response.status_code == 404


async def test_webhook_requires_secret_and_forwards_exact_event(
    client: AsyncClient,
    app: FastAPI,
) -> None:
    event_id = str(uuid4())
    payload = {
        "event_id": event_id,
        "payment_code": "PAY-123",
        "status": "PAID",
        "occurred_at": datetime.now(UTC).isoformat(),
    }
    denied = await client.post("/api/v1/payments/webhook", json=payload)
    assert denied.status_code == 403

    response = await client.post(
        "/api/v1/payments/webhook",
        headers={"X-Webhook-Secret": "test-webhook-secret"},
        json=payload,
    )

    assert response.status_code == 202
    assert response.json() == {
        "accepted": True,
        "event_id": event_id,
        "payment_code": "PAY-123",
        "status": "PAID",
    }
    assert app.state.sales_client.payments[-1]["event_id"] == event_id


async def test_webhook_validates_timezone_and_reports_sales_failure(
    client: AsyncClient,
    app: FastAPI,
) -> None:
    payload = {
        "event_id": str(uuid4()),
        "payment_code": "PAY-456",
        "status": "CANCELED",
        "occurred_at": "2026-10-15T12:00:00",
    }
    invalid = await client.post(
        "/api/v1/payments/webhook",
        headers={"X-Webhook-Secret": "test-webhook-secret"},
        json=payload,
    )
    assert invalid.status_code == 422

    payload["occurred_at"] = "2026-10-15T12:00:00Z"
    app.state.sales_client.fail_payment = True
    failed = await client.post(
        "/api/v1/payments/webhook",
        headers={"X-Webhook-Secret": "test-webhook-secret"},
        json=payload,
    )
    assert failed.status_code == 503
    assert failed.json()["error"]["code"] == "SALES_SERVICE_UNAVAILABLE"


async def test_health_endpoints(client: AsyncClient) -> None:
    live = await client.get("/health/live")
    ready = await client.get("/health/ready")

    assert live.status_code == 200
    assert live.json() == {"status": "ok"}
    assert ready.status_code == 200
    assert ready.json()["checks"]["database"] == "ok"


async def test_readiness_reports_database_failure(client: AsyncClient, app: FastAPI) -> None:
    original_factory = app.state.session_factory

    class FailingSessionContext:
        async def __aenter__(self):
            raise SQLAlchemyError("offline")

        async def __aexit__(self, *_args) -> None:
            return None

    app.state.session_factory = FailingSessionContext
    try:
        response = await client.get("/health/ready")
    finally:
        app.state.session_factory = original_factory

    assert response.status_code == 503
    assert response.json()["checks"]["database"] == "failed"
