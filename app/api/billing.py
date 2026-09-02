from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.auth import get_current_tenant
from app.models import Tenant
from app.services.stripe_service import create_pro_checkout_session


router = APIRouter(
    prefix="/billing",
    tags=["billing"]
)


class CheckoutResponse(BaseModel):
    checkout_url: str
    session_id: str


@router.post(
    "/checkout",
    response_model=CheckoutResponse
)
def create_checkout(
    tenant: Tenant = Depends(get_current_tenant)
):
    try:
        session = create_pro_checkout_session(tenant)

    except Exception as exc:
        print(f"Stripe Checkout error: {exc}")

        raise HTTPException(
            status_code=502,
            detail="Unable to create Stripe Checkout session"
        )

    return CheckoutResponse(
        checkout_url=session.url,
        session_id=session.id
    )


@router.get("/success")
def checkout_success():
    return {
        "message": (
            "Checkout completed. "
            "Subscription status will be updated by the Stripe webhook."
        )
    }


@router.get("/cancel")
def checkout_cancel():
    return {
        "message": "Checkout was cancelled."
    }