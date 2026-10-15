from httpx import AsyncClient
from sqlalchemy import select

from app.models.user import User


async def test_register_hashes_password_and_normalizes_email(client: AsyncClient, app) -> None:
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "  STUDENT@Example.com ",
            "password": "correct-horse-battery-staple",
            "full_name": "  Aluna   SOAT  ",
        },
    )

    assert response.status_code == 201
    assert response.json()["email"] == "student@example.com"
    assert response.json()["full_name"] == "Aluna SOAT"
    async with app.state.session_factory() as session:
        user = await session.scalar(select(User).where(User.email == "student@example.com"))
    assert user is not None
    assert user.password_hash != "correct-horse-battery-staple"
    assert user.password_hash.startswith("$argon2")


async def test_duplicate_registration_returns_clear_conflict(client: AsyncClient) -> None:
    payload = {
        "email": "duplicate@example.com",
        "password": "strong-password",
        "full_name": "Usuário Duplicado",
    }
    assert (await client.post("/api/v1/auth/register", json=payload)).status_code == 201

    response = await client.post("/api/v1/auth/register", json=payload)

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "EMAIL_ALREADY_EXISTS"


async def test_login_returns_bearer_token_and_rejects_wrong_password(client: AsyncClient) -> None:
    await client.post(
        "/api/v1/auth/register",
        json={
            "email": "login@example.com",
            "password": "strong-password",
            "full_name": "Login Teste",
        },
    )

    invalid = await client.post(
        "/api/v1/auth/login",
        json={"email": "login@example.com", "password": "wrong-password"},
    )
    assert invalid.status_code == 401
    assert invalid.json()["error"]["code"] == "AUTHENTICATION_REQUIRED"

    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "login@example.com", "password": "strong-password"},
    )
    assert response.status_code == 200
    assert response.json()["token_type"] == "bearer"
    assert response.json()["expires_in"] == 1800


async def test_invalid_bearer_token_is_rejected(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/vehicles",
        headers={"Authorization": "Bearer invalid-token"},
        json={
            "brand": "Ford",
            "model": "Ka",
            "year": 2020,
            "color": "Prata",
            "price": "50000.00",
        },
    )

    assert response.status_code == 401
    assert response.json()["error"]["message"] == "Token inválido"


async def test_validation_errors_use_standard_envelope(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/auth/register",
        json={"email": "invalid", "password": "short", "full_name": "A"},
    )

    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert len(body["error"]["details"]) == 3
