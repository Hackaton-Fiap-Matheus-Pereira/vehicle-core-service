from collections.abc import AsyncIterator
from typing import Any

import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.core.config import Settings
from app.core.errors import SalesServiceError
from app.db.base import Base
from app.main import create_app
from app.models.vehicle import Vehicle
from app.schemas.payment import PaymentWebhook


class MockSalesClient:
    def __init__(self) -> None:
        self.fail_sync = False
        self.fail_payment = False
        self.projections: list[dict[str, Any]] = []
        self.payments: list[dict[str, Any]] = []

    async def upsert_vehicle(self, vehicle: Vehicle) -> None:
        if self.fail_sync:
            raise SalesServiceError()
        self.projections.append(
            {
                "id": vehicle.id,
                "brand": vehicle.brand,
                "model": vehicle.model,
                "year": vehicle.year,
                "color": vehicle.color,
                "price": str(vehicle.price),
                "status": vehicle.status.value,
                "source_version": vehicle.source_version,
            }
        )

    async def forward_payment(self, payment: PaymentWebhook) -> None:
        if self.fail_payment:
            raise SalesServiceError()
        self.payments.append(payment.model_dump(mode="json"))


@pytest_asyncio.fixture
async def app() -> AsyncIterator[FastAPI]:
    settings = Settings(
        app_env="test",
        database_url="sqlite+aiosqlite:///:memory:",
        jwt_secret="test-jwt-secret-with-enough-entropy",
        service_token="test-service-token",
        webhook_secret="test-webhook-secret",
        sales_service_url="http://sales.test",
    )
    application = create_app(settings)
    async with application.state.engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    application.state.sales_client = MockSalesClient()
    yield application
    await application.state.engine.dispose()


@pytest_asyncio.fixture
async def client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as test_client:
        yield test_client


@pytest_asyncio.fixture
async def auth_headers(client: AsyncClient) -> dict[str, str]:
    register_response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "admin@example.com",
            "password": "strong-password",
            "full_name": "Admin Teste",
        },
    )
    assert register_response.status_code == 201
    login_response = await client.post(
        "/api/v1/auth/login",
        json={"email": "admin@example.com", "password": "strong-password"},
    )
    assert login_response.status_code == 200
    token = login_response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def vehicle_id(client: AsyncClient, auth_headers: dict[str, str]) -> str:
    response = await client.post(
        "/api/v1/vehicles",
        headers=auth_headers,
        json={
            "brand": "Honda",
            "model": "Civic",
            "year": 2022,
            "color": "Preto",
            "price": "109900.00",
        },
    )
    assert response.status_code == 201
    return response.json()["id"]
