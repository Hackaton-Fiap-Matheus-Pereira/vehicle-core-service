from fastapi import APIRouter, Request, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.api.deps import SessionDependency
from app.core.errors import AuthenticationError, ConflictError
from app.core.security import create_access_token, hash_password, verify_password
from app.models.user import User
from app.schemas.auth import TokenResponse, UserLogin, UserRegister, UserResponse

router = APIRouter(prefix="/auth", tags=["autenticação"])


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(payload: UserRegister, session: SessionDependency) -> User:
    existing = await session.scalar(select(User).where(User.email == str(payload.email)))
    if existing is not None:
        raise ConflictError("Já existe um usuário com este e-mail", code="EMAIL_ALREADY_EXISTS")

    user = User(
        email=str(payload.email),
        full_name=payload.full_name,
        password_hash=hash_password(payload.password),
    )
    session.add(user)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise ConflictError(
            "Já existe um usuário com este e-mail",
            code="EMAIL_ALREADY_EXISTS",
        ) from exc
    await session.refresh(user)
    return user


@router.post("/login", response_model=TokenResponse)
async def login(
    payload: UserLogin,
    request: Request,
    session: SessionDependency,
) -> TokenResponse:
    user = await session.scalar(select(User).where(User.email == str(payload.email)))
    if (
        user is None
        or not user.is_active
        or not verify_password(payload.password, user.password_hash)
    ):
        raise AuthenticationError("E-mail ou senha inválidos")

    settings = request.app.state.settings
    token, expires_in = create_access_token(
        subject=user.id,
        secret=settings.jwt_secret.get_secret_value(),
        algorithm=settings.jwt_algorithm,
        expires_minutes=settings.jwt_expire_minutes,
    )
    return TokenResponse(access_token=token, expires_in=expires_in)
