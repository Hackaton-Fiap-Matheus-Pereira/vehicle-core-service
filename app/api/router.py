from fastapi import APIRouter

from app.api.v1 import auth, payments, vehicles

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth.router)
api_router.include_router(vehicles.router)
api_router.include_router(payments.router)
