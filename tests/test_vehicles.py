from fastapi import FastAPI
from httpx import AsyncClient


def vehicle_payload(**overrides) -> dict:
    payload = {
        "brand": "Toyota",
        "model": "Corolla",
        "year": 2023,
        "color": "Prata",
        "price": "129990.90",
    }
    payload.update(overrides)
    return payload


async def test_vehicle_endpoints_require_authentication(client: AsyncClient) -> None:
    response = await client.post("/api/v1/vehicles", json=vehicle_payload())

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "AUTHENTICATION_REQUIRED"


async def test_create_and_get_vehicle_syncs_exact_projection(
    client: AsyncClient,
    app: FastAPI,
    auth_headers: dict[str, str],
) -> None:
    response = await client.post(
        "/api/v1/vehicles",
        headers=auth_headers,
        json=vehicle_payload(),
    )

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "AVAILABLE"
    assert body["sync_status"] == "SYNCED"
    assert body["source_version"] == 1

    projection = app.state.sales_client.projections[-1]
    assert projection == {
        "id": body["id"],
        "brand": "Toyota",
        "model": "Corolla",
        "year": 2023,
        "color": "Prata",
        "price": "129990.90",
        "status": "AVAILABLE",
        "source_version": 1,
    }

    fetched = await client.get(f"/api/v1/vehicles/{body['id']}", headers=auth_headers)
    assert fetched.status_code == 200
    assert fetched.json()["id"] == body["id"]


async def test_collection_get_is_not_exposed_in_core(
    client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    response = await client.get("/api/v1/vehicles", headers=auth_headers)

    assert response.status_code == 405


async def test_create_survives_sync_failure_and_retry_recovers(
    client: AsyncClient,
    app: FastAPI,
    auth_headers: dict[str, str],
) -> None:
    app.state.sales_client.fail_sync = True
    created = await client.post(
        "/api/v1/vehicles",
        headers=auth_headers,
        json=vehicle_payload(),
    )

    assert created.status_code == 201
    assert created.json()["sync_status"] == "FAILED"
    vehicle_id = created.json()["id"]

    failed_retry = await client.post(
        f"/api/v1/vehicles/{vehicle_id}/sync/retry",
        headers=auth_headers,
    )
    assert failed_retry.status_code == 503
    assert failed_retry.json()["error"]["code"] == "SALES_SERVICE_UNAVAILABLE"

    app.state.sales_client.fail_sync = False
    recovered = await client.post(
        f"/api/v1/vehicles/{vehicle_id}/sync/retry",
        headers=auth_headers,
    )
    assert recovered.status_code == 200
    assert recovered.json()["sync_status"] == "SYNCED"


async def test_patch_updates_version_and_projection(
    client: AsyncClient,
    app: FastAPI,
    auth_headers: dict[str, str],
    vehicle_id: str,
) -> None:
    response = await client.patch(
        f"/api/v1/vehicles/{vehicle_id}",
        headers=auth_headers,
        json={"price": "118000.00", "color": "Azul"},
    )

    assert response.status_code == 200
    assert response.json()["price"] == "118000.00"
    assert response.json()["source_version"] == 2
    assert response.json()["sync_status"] == "SYNCED"
    assert app.state.sales_client.projections[-1]["source_version"] == 2

    no_change = await client.patch(
        f"/api/v1/vehicles/{vehicle_id}",
        headers=auth_headers,
        json={"color": "Azul"},
    )
    assert no_change.status_code == 200
    assert no_change.json()["source_version"] == 2


async def test_patch_requires_non_null_field(
    client: AsyncClient,
    auth_headers: dict[str, str],
    vehicle_id: str,
) -> None:
    empty = await client.patch(f"/api/v1/vehicles/{vehicle_id}", headers=auth_headers, json={})
    null_field = await client.patch(
        f"/api/v1/vehicles/{vehicle_id}",
        headers=auth_headers,
        json={"brand": None},
    )

    assert empty.status_code == 422
    assert null_field.status_code == 422


async def test_missing_vehicle_returns_404(
    client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    missing_id = "00000000-0000-0000-0000-000000000000"

    response = await client.get(f"/api/v1/vehicles/{missing_id}", headers=auth_headers)

    assert response.status_code == 404
    assert response.json()["error"]["message"] == "Veículo não encontrado"
