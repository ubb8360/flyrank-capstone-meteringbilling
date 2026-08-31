import os

import stripe

from app.models import Tenant


def create_pro_checkout_session(tenant: Tenant):
    stripe_secret_key = os.getenv("STRIPE_SECRET_KEY")
    pro_price_id = os.getenv("STRIPE_PRO_PRICE_ID")

    if not stripe_secret_key:
        raise RuntimeError("STRIPE_SECRET_KEY is not set")

    if not pro_price_id:
        raise RuntimeError("STRIPE_PRO_PRICE_ID is not set")

    stripe.api_key = stripe_secret_key

    session_data = {
        "mode": "subscription",
        "line_items": [
            {
                "price": pro_price_id,
                "quantity": 1,
            }
        ],
        "success_url": (
            "http://localhost:8000/billing/success"
            "?session_id={CHECKOUT_SESSION_ID}"
        ),
        "cancel_url": "http://localhost:8000/billing/cancel",

        # Gives us an easy way to connect the Stripe
        # Checkout Session back to our tenant.
        "client_reference_id": str(tenant.id),

        "metadata": {
            "tenant_id": str(tenant.id)
        },

        "subscription_data": {
            "metadata": {
                "tenant_id": str(tenant.id)
            }
        },
    }

    # Reuse the existing Stripe customer after the
    # tenant has gone through Checkout once.
    if tenant_subscription_customer_id := getattr(
        tenant,
        "stripe_customer_id",
        None
    ):
        session_data["customer"] = tenant_subscription_customer_id

    return stripe.checkout.Session.create(**session_data)