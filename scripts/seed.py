import hashlib
import os
import uuid
from datetime import datetime, timezone

from dotenv import load_dotenv
from sqlalchemy import select

from app.database import SessionLocal
from app.models import Plan, Subscription, Tenant


load_dotenv()


def hash_api_key(api_key: str) -> str:
    return hashlib.sha256(api_key.encode("utf-8")).hexdigest()


def seed():
    db = SessionLocal()

    try:
        # -------------------------
        # Plans
        # -------------------------

        free_plan = db.execute(
            select(Plan).where(Plan.name == "free")
        ).scalar_one_or_none()

        if free_plan is None:
            free_plan = Plan(
                id=1,
                name="free",
                api_call_limit=1000,
                ai_token_limit=100000,
            )
            db.add(free_plan)

        pro_plan = db.execute(
            select(Plan).where(Plan.name == "pro")
        ).scalar_one_or_none()

        if pro_plan is None:
            pro_plan = Plan(
                id=2,
                name="pro",
                api_call_limit=10000,
                ai_token_limit=1000000,
            )
            db.add(pro_plan)

        # Make sure the plan rows exist before creating the subscription.
        db.flush()

        # -------------------------
        # Demo tenant
        # -------------------------

        demo_api_key = os.getenv("DEMO_API_KEY")

        if not demo_api_key:
            raise RuntimeError("DEMO_API_KEY is not set")

        api_key_hash = hash_api_key(demo_api_key)

        demo_tenant = db.execute(
            select(Tenant).where(Tenant.api_key_hash == api_key_hash)
        ).scalar_one_or_none()

        if demo_tenant is None:
            demo_tenant = Tenant(
                id=uuid.uuid4(),
                name="Demo Tenant",
                api_key_hash=api_key_hash,
            )
            db.add(demo_tenant)
            db.flush()

        # -------------------------
        # Demo subscription
        # -------------------------

        subscription = db.execute(
            select(Subscription).where(
                Subscription.tenant_id == demo_tenant.id
            )
        ).scalar_one_or_none()

        if subscription is None:
            subscription = Subscription(
                id=uuid.uuid4(),
                tenant_id=demo_tenant.id,
                plan_id=free_plan.id,
                status="active",
                updated_at=datetime.now(timezone.utc),
            )
            db.add(subscription)

        db.commit()

        print("Seed complete")
        print(f"Demo tenant: {demo_tenant.name}")
        print(f"Tenant ID: {demo_tenant.id}")
        print(f"Plan: {free_plan.name}")
        print(f"Demo API key: {demo_api_key}")

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()


if __name__ == "__main__":
    seed()