from typing import Annotated

from fastapi import APIRouter, Depends, Request, status

from app.api.deps import require_webhook_secret
from app.schemas.payment import PaymentWebhook, PaymentWebhookResponse

router = APIRouter(prefix="/payments", tags=["pagamentos"])


@router.post(
    "/webhook",
    response_model=PaymentWebhookResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def receive_payment_webhook(
    payload: PaymentWebhook,
    request: Request,
    _authorized: Annotated[None, Depends(require_webhook_secret)],
) -> PaymentWebhookResponse:
    await request.app.state.sales_client.forward_payment(payload)
    return PaymentWebhookResponse(
        accepted=True,
        event_id=payload.event_id,
        payment_code=payload.payment_code,
        status=payload.status,
    )
