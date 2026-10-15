from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field, field_validator


class PaymentStatus(StrEnum):
    PAID = "PAID"
    CANCELED = "CANCELED"


class PaymentWebhook(BaseModel):
    event_id: str = Field(min_length=1, max_length=128)
    payment_code: str = Field(min_length=1, max_length=64)
    status: PaymentStatus
    occurred_at: datetime

    @field_validator("event_id", "payment_code")
    @classmethod
    def validate_identifier(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("identificador não pode ser vazio")
        return normalized

    @field_validator("occurred_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("occurred_at deve conter fuso horário")
        return value


class PaymentWebhookResponse(BaseModel):
    accepted: bool
    event_id: str
    payment_code: str
    status: PaymentStatus
