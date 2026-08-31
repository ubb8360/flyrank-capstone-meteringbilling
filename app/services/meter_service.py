import uuid

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Tenant, UsageEvent
from app.repositories.subscription_repo import get_subscription_with_plan
from app.repositories.usage_repo import (
    create_usage_event,
    get_by_idempotency_key,
    get_monthly_api_usage,
)


class QuotaExceededError(Exception):
    pass


class SubscriptionUnavailableError(Exception):
    pass


def record_api_call(
    db: Session,
    tenant: Tenant,
    idempotency_key: str
) -> UsageEvent:

    # Check if this request was already recorded.
    existing_event = get_by_idempotency_key(
        db,
        tenant.id,
        idempotency_key
    )

    if existing_event is not None:
        return existing_event

    # Load the tenant's subscription and plan.
    subscription_data = get_subscription_with_plan(
        db,
        tenant.id
    )

    if subscription_data is None:
        raise SubscriptionUnavailableError(
            "Tenant does not have a subscription."
        )

    subscription, plan = subscription_data

    if subscription.status != "active":
        raise SubscriptionUnavailableError(
            "Subscription is not active."
        )

    # Check current API-call usage.
    current_usage = get_monthly_api_usage(
        db,
        tenant.id
    )

    requested_usage = 1

    if current_usage + requested_usage > plan.api_call_limit:
        raise QuotaExceededError(
            "Monthly API call quota exceeded."
        )

    usage_event = UsageEvent(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        usage_type="api_call",
        quantity=1,

        # API-call pricing will be added later.
        cost_microusd=0,

        idempotency_key=idempotency_key
    )

    try:
        return create_usage_event(
            db,
            usage_event
        )

    except IntegrityError:
        db.rollback()

        # Another copy of the same request may have been
        # inserted between our first check and the insert.
        existing_event = get_by_idempotency_key(
            db,
            tenant.id,
            idempotency_key
        )

        if existing_event is not None:
            return existing_event

        raise