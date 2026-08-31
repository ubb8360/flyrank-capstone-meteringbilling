from fastapi import (
    APIRouter,
    Depends,
    Header,
    HTTPException,
    status,
)
from sqlalchemy.orm import Session

from app.auth import get_current_tenant
from app.database import get_db
from app.models import Tenant
from app.schemas import GenerateRequest, GenerateResponse
from app.services.meter_service import (
    QuotaExceededError,
    SubscriptionUnavailableError,
    record_api_call,
)


router = APIRouter(
    tags=["usage"]
)


@router.post(
    "/generate",
    response_model=GenerateResponse
)
def generate(
    request: GenerateRequest,
    idempotency_key: str = Header(
        ...,
        alias="Idempotency-Key",
        min_length=1,
        max_length=255
    ),
    tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
):
    try:
        event = record_api_call(
            db=db,
            tenant=tenant,
            idempotency_key=idempotency_key
        )

    except QuotaExceededError as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=str(exc)
        )

    except SubscriptionUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=str(exc)
        )

    return GenerateResponse(
        event_id=event.id,
        usage_type=event.usage_type,
        quantity=event.quantity,
        cost_microusd=event.cost_microusd,
        idempotency_key=event.idempotency_key
    )