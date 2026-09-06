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
from app.schemas import (
    GenerateRequest,
    GenerateResponse,
    UsageAmount,
    UsageSummaryResponse,
)
from app.services.meter_service import (
    QuotaExceededError,
    SubscriptionUnavailableError,
    record_api_call,
    record_ai_tokens,
)
from app.repositories.subscription_repo import (
    get_subscription_with_plan,
)
from app.repositories.usage_repo import (
    get_monthly_api_usage,
    get_monthly_ai_usage,
    get_monthly_cost_microusd,
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
    
@router.get(
    "/usage",
    response_model=UsageSummaryResponse,
)
def get_usage(
    tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
):
    subscription_data = get_subscription_with_plan(
        db,
        tenant.id,
    )

    if subscription_data is None:
        raise HTTPException(
            status_code=404,
            detail="Subscription was not found.",
        )

    subscription, plan = subscription_data

    api_calls_used = get_monthly_api_usage(
        db,
        tenant.id,
    )

    ai_tokens_used = get_monthly_ai_usage(
        db,
        tenant.id,
    )

    total_cost_microusd = get_monthly_cost_microusd(
        db,
        tenant.id,
    )

    return UsageSummaryResponse(
        tenant_id=tenant.id,
        plan=plan.name,
        subscription_status=subscription.status,

        api_calls=UsageAmount(
            used=api_calls_used,
            limit=plan.api_call_limit,
        ),

        ai_tokens=UsageAmount(
            used=ai_tokens_used,
            limit=plan.ai_token_limit,
        ),

        total_cost_microusd=total_cost_microusd,
    )