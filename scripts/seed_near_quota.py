import os
import uuid

from dotenv import load_dotenv
from sqlalchemy import select

from app.auth import hash_api_key
from app.database import SessionLocal
from app.models import Tenant, UsageEvent
from app.repositories.usage_repo import get_monthly_api_usage


load_dotenv()

TARGET_USAGE = 999


def seed_near_quota():
    db = SessionLocal()

    try:
        demo_api_key = os.getenv("DEMO_API_KEY")

        if not demo_api_key:
            raise RuntimeError("DEMO_API_KEY is not set")

        api_key_hash = hash_api_key(demo_api_key)

        tenant = db.execute(
            select(Tenant).where(
                Tenant.api_key_hash == api_key_hash
            )
        ).scalar_one_or_none()

        if tenant is None:
            raise RuntimeError(
                "Demo tenant was not found. Run the normal seed first."
            )

        current_usage = get_monthly_api_usage(
            db,
            tenant.id
        )

        if current_usage > TARGET_USAGE:
            raise RuntimeError(
                f"Current API usage is already {current_usage}. "
                f"Cannot seed down to {TARGET_USAGE}."
            )

        amount_to_add = TARGET_USAGE - current_usage

        if amount_to_add == 0:
            print("Demo tenant is already at 999 API calls.")
            return

        events = []

        for _ in range(amount_to_add):
            event = UsageEvent(
                id=uuid.uuid4(),
                tenant_id=tenant.id,
                usage_type="api_call",
                quantity=1,
                cost_microusd=0,
                idempotency_key=f"quota-seed-{uuid.uuid4()}",
            )

            events.append(event)

        db.add_all(events)
        db.commit()

        final_usage = get_monthly_api_usage(
            db,
            tenant.id
        )

        print("Near-quota seed complete")
        print(f"Previous usage: {current_usage}")
        print(f"Added events: {amount_to_add}")
        print(f"Current usage: {final_usage}")

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()


if __name__ == "__main__":
    seed_near_quota()