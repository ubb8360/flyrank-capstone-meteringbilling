import os

import stripe
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.repositories.stripe_event_repo import (
    add_stripe_event,
    get_stripe_event,
)


router = APIRouter(
    prefix="/webhooks",
    tags=["webhooks"]
)


@router.post("/stripe")
async def stripe_webhook(
    request: Request,
    db: Session = Depends(get_db),
):
    webhook_secret = os.getenv(
        "STRIPE_WEBHOOK_SECRET"
    )

    if not webhook_secret:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Stripe webhook secret is not configured."
        )

    # Stripe requires the original raw request body
    # for signature verification.
    payload = await request.body()

    signature = request.headers.get(
        "Stripe-Signature"
    )

    if not signature:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing Stripe signature."
        )

    try:
        event = stripe.Webhook.construct_event(
            payload,
            signature,
            webhook_secret
        )

    except (ValueError, stripe.error.SignatureVerificationError):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid Stripe webhook signature."
        )

    event_id = event["id"]
    event_type = event["type"]

    existing_event = get_stripe_event(
        db,
        event_id
    )

    if existing_event is not None:
        return {
            "status": "duplicate",
            "event_id": event_id
        }

    add_stripe_event(
        db=db,
        event_id=event_id,
        event_type=event_type
    )

    try:
        db.commit()

    except IntegrityError:
        db.rollback()

        # Another request may have inserted the
        # same Stripe event at nearly the same time.
        existing_event = get_stripe_event(
            db,
            event_id
        )

        if existing_event is not None:
            return {
                "status": "duplicate",
                "event_id": event_id
            }

        raise

    return {
        "status": "processed",
        "event_id": event_id,
        "event_type": event_type
    }