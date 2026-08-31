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
    record_ai_tokens,
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
        if request.usage_type == "api_call":
            event = record_api_call(
                db=db,
                tenant=tenant,
                idempotency_key=idempotency_key
            )

        else:
            event = record_ai_tokens(
                db=db,
                tenant=tenant,
                idempotency_key=idempotency_key,
                input_tokens=request.input_tokens or 0,
                cached_input_tokens=request.cached_input_tokens or 0,
                output_tokens=request.output_tokens or 0,
                reasoning_tokens=request.reasoning_tokens or 0,
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

    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc)
        )

    return GenerateResponse(
        event_id=event.id,
        usage_type=event.usage_type,
        quantity=event.quantity,
        cost_microusd=event.cost_microusd,
        idempotency_key=event.idempotency_key,
        input_tokens=event.input_tokens,
        cached_input_tokens=event.cached_input_tokens,
        output_tokens=event.output_tokens,
        reasoning_tokens=event.reasoning_tokens,
    )