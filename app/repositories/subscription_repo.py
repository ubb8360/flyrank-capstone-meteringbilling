from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Plan, Subscription


def get_subscription_with_plan(
    db: Session,
    tenant_id
):
    result = db.execute(
        select(Subscription, Plan)
        .join(
            Plan,
            Subscription.plan_id == Plan.id
        )
        .where(
            Subscription.tenant_id == tenant_id
        )
    )

    row = result.one_or_none()

    if row is None:
        return None

    subscription, plan = row

    return subscription, plan