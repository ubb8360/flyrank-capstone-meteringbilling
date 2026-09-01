from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import StripeEvent


def get_stripe_event(
    db: Session,
    event_id: str
) -> StripeEvent | None:
    result = db.execute(
        select(StripeEvent).where(
            StripeEvent.id == event_id
        )
    )

    return result.scalar_one_or_none()


def add_stripe_event(
    db: Session,
    event_id: str,
    event_type: str
) -> StripeEvent:
    stripe_event = StripeEvent(
        id=event_id,
        event_type=event_type
    )

    db.add(stripe_event)

    return stripe_event