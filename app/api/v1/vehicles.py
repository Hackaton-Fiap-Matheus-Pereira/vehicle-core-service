import logging

from fastapi import APIRouter, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, SessionDependency
from app.core.errors import NotFoundError, SalesServiceError
from app.models.vehicle import SyncStatus, Vehicle
from app.schemas.vehicle import (
    VehicleCreate,
    VehicleResponse,
    VehicleUpdate,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/vehicles", tags=["veículos"])


async def _get_vehicle(session: AsyncSession, vehicle_id: str) -> Vehicle:
    vehicle = await session.get(Vehicle, vehicle_id)
    if vehicle is None:
        raise NotFoundError("Veículo")
    return vehicle


async def _sync_vehicle(
    *,
    request: Request,
    session: AsyncSession,
    vehicle: Vehicle,
    strict: bool,
) -> Vehicle:
    try:
        await request.app.state.sales_client.upsert_vehicle(vehicle)
    except SalesServiceError:
        vehicle.sync_status = SyncStatus.FAILED
        await session.commit()
        await session.refresh(vehicle)
        logger.warning("Falha ao sincronizar veículo %s com o serviço de vendas", vehicle.id)
        if strict:
            raise
    else:
        vehicle.sync_status = SyncStatus.SYNCED
        await session.commit()
        await session.refresh(vehicle)
    return vehicle


@router.post("", response_model=VehicleResponse, status_code=status.HTTP_201_CREATED)
async def create_vehicle(
    payload: VehicleCreate,
    request: Request,
    session: SessionDependency,
    current_user: CurrentUser,
) -> Vehicle:
    vehicle = Vehicle(
        **payload.model_dump(),
        created_by_user_id=current_user.id,
        sync_status=SyncStatus.PENDING,
        source_version=1,
    )
    session.add(vehicle)
    await session.commit()
    await session.refresh(vehicle)
    return await _sync_vehicle(request=request, session=session, vehicle=vehicle, strict=False)


@router.get("/{vehicle_id}", response_model=VehicleResponse)
async def get_vehicle(
    vehicle_id: str,
    session: SessionDependency,
    _current_user: CurrentUser,
) -> Vehicle:
    return await _get_vehicle(session, vehicle_id)


@router.patch("/{vehicle_id}", response_model=VehicleResponse)
async def update_vehicle(
    vehicle_id: str,
    payload: VehicleUpdate,
    request: Request,
    session: SessionDependency,
    _current_user: CurrentUser,
) -> Vehicle:
    vehicle = await _get_vehicle(session, vehicle_id)
    changed = False
    for field, value in payload.model_dump(exclude_unset=True).items():
        if getattr(vehicle, field) != value:
            setattr(vehicle, field, value)
            changed = True

    if not changed:
        return vehicle

    vehicle.source_version += 1
    vehicle.sync_status = SyncStatus.PENDING
    await session.commit()
    await session.refresh(vehicle)
    return await _sync_vehicle(request=request, session=session, vehicle=vehicle, strict=False)


@router.post("/{vehicle_id}/sync/retry", response_model=VehicleResponse)
async def retry_vehicle_sync(
    vehicle_id: str,
    request: Request,
    session: SessionDependency,
    _current_user: CurrentUser,
) -> Vehicle:
    vehicle = await _get_vehicle(session, vehicle_id)
    vehicle.sync_status = SyncStatus.PENDING
    await session.commit()
    await session.refresh(vehicle)
    return await _sync_vehicle(request=request, session=session, vehicle=vehicle, strict=True)
