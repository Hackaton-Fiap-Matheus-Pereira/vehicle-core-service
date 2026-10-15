from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.deps import SessionDependency, require_service_token
from app.core.errors import NotFoundError
from app.models.vehicle import SyncStatus, Vehicle
from app.schemas.vehicle import VehicleResponse, VehicleStatusUpdate

router = APIRouter(prefix="/internal/v1", tags=["integração interna"])


@router.put("/vehicles/{vehicle_id}/status", response_model=VehicleResponse)
async def update_vehicle_status(
    vehicle_id: str,
    payload: VehicleStatusUpdate,
    session: SessionDependency,
    _authorized: Annotated[None, Depends(require_service_token)],
) -> Vehicle:
    vehicle = await session.get(Vehicle, vehicle_id)
    if vehicle is None:
        raise NotFoundError("Veículo")

    if vehicle.status != payload.status:
        vehicle.status = payload.status
        vehicle.source_version += 1
    vehicle.sync_status = SyncStatus.SYNCED
    await session.commit()
    await session.refresh(vehicle)
    return vehicle
