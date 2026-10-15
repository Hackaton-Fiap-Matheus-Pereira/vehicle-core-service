import pytest
from pydantic import ValidationError

from app.core.config import Settings
from app.core.errors import AuthenticationError
from app.core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)


def test_argon2_hash_and_verify() -> None:
    password_hash = hash_password("secure-password")

    assert password_hash.startswith("$argon2")
    assert verify_password("secure-password", password_hash) is True
    assert verify_password("wrong-password", password_hash) is False
    assert verify_password("secure-password", "not-a-valid-hash") is False


def test_jwt_decode_rejects_expired_and_invalid_tokens() -> None:
    secret = "test-jwt-secret-with-at-least-32-bytes"
    expired, _ = create_access_token(
        subject="user-1",
        secret=secret,
        algorithm="HS256",
        expires_minutes=-1,
    )
    with pytest.raises(AuthenticationError, match="Token expirado"):
        decode_access_token(token=expired, secret=secret, algorithm="HS256")

    with pytest.raises(AuthenticationError, match="Token inválido"):
        decode_access_token(token="not-a-token", secret=secret, algorithm="HS256")


def test_production_rejects_default_secrets() -> None:
    with pytest.raises(ValidationError, match="segredos padrão"):
        Settings(app_env="production")
