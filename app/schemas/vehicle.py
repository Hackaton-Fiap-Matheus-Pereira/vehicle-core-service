from datetime import UTC, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.vehicle import SyncStatus, VehicleStatus


class VehicleFields(BaseModel):
    brand: str = Field(min_length=1, max_length=80)
    model: str = Field(min_length=1, max_length=120)
    year: int = Field(ge=1886)
    color: str = Field(min_length=1, max_length=50)
    price: Decimal = Field(gt=0, max_digits=12, decimal_places=2)

    @field_validator("brand", "model", "color")
    @classmethod
    def normalize_text(cls, value: str) -> str:
        normalized = " ".join(value.split())
        if not normalized:
            raise ValueError("não pode conter apenas espaços")
        return normalized

    @field_validator("year")
    @classmethod
    def validate_year(cls, value: int) -> int:
        if value > datetime.now(UTC).year + 1:
            raise ValueError("ano não pode ser superior ao próximo ano")
        return value


class VehicleCreate(VehicleFields):
    pass


class VehicleUpdate(BaseModel):
    brand: str | None = Field(default=None, min_length=1, max_length=80)
    model: str | None = Field(default=None, min_length=1, max_length=120)
    year: int | None = Field(default=None, ge=1886)
    color: str | None = Field(default=None, min_length=1, max_length=50)
    price: Decimal | None = Field(default=None, gt=0, max_digits=12, decimal_places=2)

    @field_validator("brand", "model", "color")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = " ".join(value.split())
        if not normalized:
            raise ValueError("não pode conter apenas espaços")
        return normalized

    @field_validator("year")
    @classmethod
    def validate_optional_year(cls, value: int | None) -> int | None:
        if value is not None and value > datetime.now(UTC).year + 1:
            raise ValueError("ano não pode ser superior ao próximo ano")
        return value

    @model_validator(mode="after")
    def ensure_at_least_one_field(self) -> "VehicleUpdate":
        if not self.model_fields_set:
            raise ValueError("informe ao menos um campo para atualização")
        if any(getattr(self, field) is None for field in self.model_fields_set):
            raise ValueError("campos de atualização não podem ser nulos")
        return self


class VehicleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    brand: str
    model: str
    year: int
    color: str
    price: Decimal
    status: VehicleStatus
    sync_status: SyncStatus
    source_version: int
    created_at: datetime
    updated_at: datetime


class VehicleStatusUpdate(BaseModel):
    status: VehicleStatus
