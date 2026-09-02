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

def get_plan_by_name(db: Session, plan_name: str):
    result = db.execute(
        select(Plan).where(
            Plan.name == plan_name
        )
    )
    return result.scalar_one_or_none()

def update_subscription_from_checkout(
    db: Session,
    tenant_id,
    stripe_customer_id: str,
    stripe_subscription_id: str,
):
    subscription_data = get_subscription_with_plan(
        db,
        tenant_id
    )

    if subscription_data is None:
        return None

    subscription, _ = subscription_data

    pro_plan = get_plan_by_name(
        db,
        "pro"
    )

    if pro_plan is None:
        raise RuntimeError(
            "Pro plan was not found."
        )

    subscription.plan_id = pro_plan.id
    subscription.status = "active"
    subscription.stripe_customer_id = stripe_customer_id
    subscription.stripe_subscription_id = stripe_subscription_id

    return subscription