import hmac
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, Header, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AuthenticationError, ForbiddenError
from app.core.security import decode_access_token
from app.models.user import User

bearer_scheme = HTTPBearer(auto_error=False)


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    async with request.app.state.session_factory() as session:
        yield session


SessionDependency = Annotated[AsyncSession, Depends(get_session)]


async def get_current_user(
    request: Request,
    session: SessionDependency,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> User:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise AuthenticationError()

    settings = request.app.state.settings
    user_id = decode_access_token(
        token=credentials.credentials,
        secret=settings.jwt_secret.get_secret_value(),
        algorithm=settings.jwt_algorithm,
    )
    user = await session.get(User, user_id)
    if user is None or not user.is_active:
        raise AuthenticationError()
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def _valid_secret(received: str | None, expected: str) -> bool:
    return received is not None and hmac.compare_digest(received, expected)


async def require_service_token(
    request: Request,
    x_service_token: Annotated[str | None, Header(alias="X-Service-Token")] = None,
) -> None:
    expected = request.app.state.settings.service_token.get_secret_value()
    if not _valid_secret(x_service_token, expected):
        raise ForbiddenError("Token interno inválido")


async def require_webhook_secret(
    request: Request,
    x_webhook_secret: Annotated[str | None, Header(alias="X-Webhook-Secret")] = None,
) -> None:
    expected = request.app.state.settings.webhook_secret.get_secret_value()
    if not _valid_secret(x_webhook_secret, expected):
        raise ForbiddenError("Segredo do webhook inválido")
