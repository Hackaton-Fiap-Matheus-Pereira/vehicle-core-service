import json
from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest

from app.core.errors import SalesServiceError
from app.models.vehicle import VehicleStatus
from app.schemas.payment import PaymentStatus, PaymentWebhook
from app.services.sales_client import SalesClient


def build_client(transport: httpx.AsyncBaseTransport) -> SalesClient:
    return SalesClient(
        base_url="http://sales.test/",
        service_token="internal-token",
        timeout_seconds=2,
        transport=transport,
    )


async def test_sales_client_sends_exact_internal_contract() -> None:
    requests: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(204)

    client = build_client(httpx.MockTransport(handler))
    vehicle = SimpleNamespace(
        id="vehicle-1",
        brand="Fiat",
        model="Pulse",
        year=2024,
        color="Branco",
        price=Decimal("99000.00"),
        status=VehicleStatus.AVAILABLE,
        source_version=3,
    )
    await client.upsert_vehicle(vehicle)

    request = requests[0]
    assert request.method == "PUT"
    assert request.url.path == "/internal/v1/vehicles/vehicle-1"
    assert request.headers["X-Service-Token"] == "internal-token"
    assert json.loads(request.content) == {
        "brand": "Fiat",
        "model": "Pulse",
        "year": 2024,
        "color": "Branco",
        "price": "99000.00",
        "status": "AVAILABLE",
        "source_version": 3,
    }


async def test_sales_client_forwards_payment_contract() -> None:
    requests: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(202)

    client = build_client(httpx.MockTransport(handler))
    event_id = str(uuid4())
    occurred_at = datetime.now(UTC)
    await client.forward_payment(
        PaymentWebhook(
            event_id=event_id,
            payment_code="PAY-900",
            status=PaymentStatus.CANCELED,
            occurred_at=occurred_at,
        )
    )

    request = requests[0]
    payload = json.loads(request.content)
    assert request.method == "POST"
    assert request.url.path == "/internal/v1/payments"
    assert request.headers["X-Service-Token"] == "internal-token"
    assert payload == {
        "event_id": event_id,
        "payment_code": "PAY-900",
        "status": "CANCELED",
        "occurred_at": occurred_at.isoformat().replace("+00:00", "Z"),
    }


async def test_sales_client_maps_downstream_and_network_errors() -> None:
    async def rejected(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(409)

    rejected_client = build_client(httpx.MockTransport(rejected))
    payment = PaymentWebhook(
        event_id=str(uuid4()),
        payment_code="PAY-901",
        status=PaymentStatus.PAID,
        occurred_at=datetime.now(UTC),
    )
    with pytest.raises(SalesServiceError) as rejected_error:
        await rejected_client.forward_payment(payment)
    assert rejected_error.value.details == {"downstream_status": 409}

    async def unavailable(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("offline", request=request)

    unavailable_client = build_client(httpx.MockTransport(unavailable))
    with pytest.raises(SalesServiceError) as network_error:
        await unavailable_client.forward_payment(payment)
    assert network_error.value.details == {"reason": "ConnectError"}
