import os
from uuid import UUID

import stripe
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.repositories.stripe_event_repo import (
    add_stripe_event,
    get_stripe_event,
)
from app.repositories.subscription_repo import (
    update_subscription_from_checkout,
)


router = APIRouter(
    prefix="/webhooks",
    tags=["webhooks"],
)


@router.post("/stripe")
async def stripe_webhook(
    request: Request,
    db: Session = Depends(get_db),
):
    webhook_secret = os.getenv("STRIPE_WEBHOOK_SECRET")

    if not webhook_secret:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Stripe webhook secret is not configured.",
        )

    # Stripe requires the original raw request body
    # for signature verification.
    payload = await request.body()

    signature = request.headers.get("Stripe-Signature")

    if not signature:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing Stripe signature.",
        )

    try:
        event = stripe.Webhook.construct_event(
            payload,
            signature,
            webhook_secret,
        )

    except (ValueError, stripe.error.SignatureVerificationError):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid Stripe webhook signature.",
        )

    event_id = event["id"]
    event_type = event["type"]

    existing_event = get_stripe_event(
        db,
        event_id,
    )

    if existing_event is not None:
        return {
            "status": "duplicate",
            "event_id": event_id,
        }

    if event_type == "checkout.session.completed":
        session = event["data"]["object"].to_dict()

        # This project only handles subscription Checkout sessions.
        # Other Checkout events are valid Stripe events but are not
        # related to our Pro upgrade flow.
        if session.get("mode") != "subscription":
            add_stripe_event(
                db=db,
                event_id=event_id,
                event_type=event_type,
            )

            db.commit()

            return {
                "status": "ignored",
                "event_id": event_id,
                "reason": "Checkout session is not a subscription.",
            }

        tenant_id = session.get("metadata", {}).get("tenant_id")
        stripe_customer_id = session.get("customer")
        stripe_subscription_id = session.get("subscription")

        if not tenant_id:
            raise HTTPException(
                status_code=400,
                detail="Checkout session is missing tenant metadata.",
            )

        if not stripe_customer_id:
            raise HTTPException(
                status_code=400,
                detail="Checkout session is missing Stripe customer.",
            )

        if not stripe_subscription_id:
            raise HTTPException(
                status_code=400,
                detail="Checkout session is missing Stripe subscription.",
            )

        try:
            parsed_tenant_id = UUID(tenant_id)
        except (ValueError, TypeError):
            raise HTTPException(
                status_code=400,
                detail="Checkout session has an invalid tenant ID.",
            )

        updated_subscription = update_subscription_from_checkout(
            db=db,
            tenant_id=parsed_tenant_id,
            stripe_customer_id=stripe_customer_id,
            stripe_subscription_id=stripe_subscription_id,
        )

        if updated_subscription is None:
            raise HTTPException(
                status_code=400,
                detail="Tenant subscription was not found.",
            )

    add_stripe_event(
        db=db,
        event_id=event_id,
        event_type=event_type,
    )

    try:
        db.commit()

    except IntegrityError:
        db.rollback()

        # Another request may have inserted the
        # same Stripe event at nearly the same time.
        existing_event = get_stripe_event(
            db,
            event_id,
        )

        if existing_event is not None:
            return {
                "status": "duplicate",
                "event_id": event_id,
            }

        raise

    return {
        "status": "processed",
        "event_id": event_id,
        "event_type": event_type,
    }