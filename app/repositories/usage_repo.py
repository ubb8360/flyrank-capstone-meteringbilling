from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import UsageEvent


def get_by_idempotency_key(
    db: Session,
    tenant_id,
    idempotency_key: str
):
    result = db.execute(
        select(UsageEvent).where(
            UsageEvent.tenant_id == tenant_id,
            UsageEvent.idempotency_key == idempotency_key
        )
    )

    return result.scalar_one_or_none()


def get_monthly_api_usage(
    db: Session,
    tenant_id
) -> int:
    now = datetime.now(timezone.utc)

    month_start = now.replace(
        day=1,
        hour=0,
        minute=0,
        second=0,
        microsecond=0
    )

    result = db.execute(
        select(
            func.coalesce(
                func.sum(UsageEvent.quantity),
                0
            )
        ).where(
            UsageEvent.tenant_id == tenant_id,
            UsageEvent.usage_type == "api_call",
            UsageEvent.created_at >= month_start
        )
    )

    return int(result.scalar_one())

def get_monthly_ai_usage(
    db: Session,
    tenant_id
) -> int:
    now = datetime.now(timezone.utc)

    month_start = now.replace(
        day=1,
        hour=0,
        minute=0,
        second=0,
        microsecond=0
    )

    result = db.execute(
        select(
            func.coalesce(
                func.sum(UsageEvent.quantity),
                0
            )
        ).where(
            UsageEvent.tenant_id == tenant_id,
            UsageEvent.usage_type == "ai_tokens",
            UsageEvent.created_at >= month_start
        )
    )

    return int(result.scalar_one())


def create_usage_event(
    db: Session,
    usage_event: UsageEvent
) -> UsageEvent:
    db.add(usage_event)
    db.commit()
    db.refresh(usage_event)

    return usage_event