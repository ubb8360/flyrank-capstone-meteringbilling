import logging
import time

from sqlalchemy import select

from app.database import SessionLocal
from app.models import Tenant
from app.repositories.usage_repo import (
    get_monthly_ai_usage,
    get_monthly_api_usage,
    get_monthly_cost_microusd,
)


logger = logging.getLogger(__name__)

MAX_ATTEMPTS = 3
RETRY_DELAY_SECONDS = 2


def reconcile_usage():
    db = SessionLocal()

    try:
        tenants = db.execute(
            select(Tenant)
        ).scalars().all()

        logger.info(
            "Starting usage reconciliation for %s tenants.",
            len(tenants),
        )

        for tenant in tenants:
            api_usage = get_monthly_api_usage(
                db,
                tenant.id,
            )

            ai_usage = get_monthly_ai_usage(
                db,
                tenant.id,
            )

            cost_microusd = get_monthly_cost_microusd(
                db,
                tenant.id,
            )

            logger.info(
                (
                    "tenant=%s "
                    "api_calls=%s "
                    "ai_tokens=%s "
                    "cost_microusd=%s"
                ),
                tenant.id,
                api_usage,
                ai_usage,
                cost_microusd,
            )

        logger.info("Usage reconciliation completed.")

    finally:
        db.close()


def run_with_retries():
    for attempt in range(
        1,
        MAX_ATTEMPTS + 1,
    ):
        try:
            reconcile_usage()
            return

        except Exception:
            logger.exception(
                "Usage reconciliation failed on attempt %s/%s.",
                attempt,
                MAX_ATTEMPTS,
            )

            if attempt == MAX_ATTEMPTS:
                raise

            time.sleep(RETRY_DELAY_SECONDS)