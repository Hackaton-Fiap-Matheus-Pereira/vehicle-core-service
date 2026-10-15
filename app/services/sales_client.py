from typing import Any

import httpx

from app.core.errors import SalesServiceError
from app.models.vehicle import Vehicle
from app.schemas.payment import PaymentWebhook


class SalesClient:
    def __init__(
        self,
        *,
        base_url: str,
        service_token: str,
        timeout_seconds: float,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.service_token = service_token
        self.timeout_seconds = timeout_seconds
        self.transport = transport

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json: dict[str, Any],
    ) -> httpx.Response:
        try:
            async with httpx.AsyncClient(
                base_url=self.base_url,
                timeout=self.timeout_seconds,
                transport=self.transport,
            ) as client:
                response = await client.request(
                    method,
                    path,
                    json=json,
                    headers={"X-Service-Token": self.service_token},
                )
        except httpx.RequestError as exc:
            raise SalesServiceError(details={"reason": type(exc).__name__}) from exc

        if not response.is_success:
            raise SalesServiceError(
                "O serviço de vendas rejeitou a solicitação",
                details={"downstream_status": response.status_code},
            )
        return response

    async def upsert_vehicle(self, vehicle: Vehicle) -> None:
        payload = {
            "brand": vehicle.brand,
            "model": vehicle.model,
            "year": vehicle.year,
            "color": vehicle.color,
            "price": str(vehicle.price),
            "status": vehicle.status.value,
            "source_version": vehicle.source_version,
        }
        await self._request("PUT", f"/internal/v1/vehicles/{vehicle.id}", json=payload)

    async def forward_payment(self, payment: PaymentWebhook) -> None:
        await self._request(
            "POST",
            "/internal/v1/payments",
            json=payment.model_dump(mode="json"),
        )
