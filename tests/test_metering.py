import hashlib
import uuid

import pytest
from sqlalchemy import delete, func, select

from app.database import SessionLocal
from app.models import Plan, Subscription, Tenant, UsageEvent
from app.services.meter_service import (
    QuotaExceededError,
    SubscriptionUnavailableError,
    record_api_call,
)


@pytest.fixture
def test_account():
    """
    Creates a temporary tenant with a very small quota.

    The API-call limit is only 2 so the quota tests do not
    need hundreds or thousands of usage events.
    """
    db = SessionLocal()

    suffix = uuid.uuid4().hex[:8]

    # Use a high random ID so we do not conflict with
    # the seeded Free (1) and Pro (2) plans.
    plan_id = 10000 + (uuid.uuid4().int % 1000000000)

    plan = Plan(
        id=plan_id,
        name=f"test-plan-{suffix}",
        api_call_limit=2,
        ai_token_limit=1000,
    )

    test_api_key = f"test-key-{suffix}"

    api_key_hash = hashlib.sha256(
        test_api_key.encode("utf-8")
    ).hexdigest()

    tenant = Tenant(
        id=uuid.uuid4(),
        name=f"Test Tenant {suffix}",
        api_key_hash=api_key_hash,
    )

    db.add_all([plan, tenant])
    db.flush()

    subscription = Subscription(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        plan_id=plan.id,
        status="active",
    )

    db.add(subscription)
    db.commit()

    try:
        yield db, tenant, subscription, plan

    finally:
        # Clean up everything this test created.
        db.rollback()

        db.execute(
            delete(UsageEvent).where(
                UsageEvent.tenant_id == tenant.id
            )
        )

        db.execute(
            delete(Subscription).where(
                Subscription.tenant_id == tenant.id
            )
        )

        db.execute(
            delete(Tenant).where(
                Tenant.id == tenant.id
            )
        )

        db.execute(
            delete(Plan).where(
                Plan.id == plan.id
            )
        )

        db.commit()
        db.close()


def test_duplicate_idempotency_key_creates_one_event(test_account):
    db, tenant, _, _ = test_account

    first_event = record_api_call(
        db=db,
        tenant=tenant,
        idempotency_key="duplicate-test-001",
    )

    second_event = record_api_call(
        db=db,
        tenant=tenant,
        idempotency_key="duplicate-test-001",
    )

    assert first_event.id == second_event.id

    event_count = db.execute(
        select(func.count())
        .select_from(UsageEvent)
        .where(
            UsageEvent.tenant_id == tenant.id,
            UsageEvent.idempotency_key == "duplicate-test-001",
        )
    ).scalar_one()

    assert event_count == 1


def test_request_at_exact_quota_is_allowed(test_account):
    db, tenant, _, plan = test_account

    first_event = record_api_call(
        db=db,
        tenant=tenant,
        idempotency_key="boundary-test-001",
    )

    second_event = record_api_call(
        db=db,
        tenant=tenant,
        idempotency_key="boundary-test-002",
    )

    assert first_event.quantity == 1
    assert second_event.quantity == 1

    total_usage = db.execute(
        select(
            func.coalesce(
                func.sum(UsageEvent.quantity),
                0
            )
        ).where(
            UsageEvent.tenant_id == tenant.id,
            UsageEvent.usage_type == "api_call",
        )
    ).scalar_one()

    assert total_usage == plan.api_call_limit
    assert total_usage == 2


def test_request_over_quota_is_rejected(test_account):
    db, tenant, _, _ = test_account

    record_api_call(
        db=db,
        tenant=tenant,
        idempotency_key="over-test-001",
    )

    record_api_call(
        db=db,
        tenant=tenant,
        idempotency_key="over-test-002",
    )

    with pytest.raises(
        QuotaExceededError,
        match="Monthly API call quota exceeded"
    ):
        record_api_call(
            db=db,
            tenant=tenant,
            idempotency_key="over-test-003",
        )

    event_count = db.execute(
        select(func.count())
        .select_from(UsageEvent)
        .where(
            UsageEvent.tenant_id == tenant.id
        )
    ).scalar_one()

    assert event_count == 2

    rejected_event_count = db.execute(
        select(func.count())
        .select_from(UsageEvent)
        .where(
            UsageEvent.tenant_id == tenant.id,
            UsageEvent.idempotency_key == "over-test-003",
        )
    ).scalar_one()

    assert rejected_event_count == 0


def test_inactive_subscription_is_rejected(test_account):
    db, tenant, subscription, _ = test_account

    subscription.status = "inactive"
    db.commit()

    with pytest.raises(
        SubscriptionUnavailableError,
        match="Subscription is not active"
    ):
        record_api_call(
            db=db,
            tenant=tenant,
            idempotency_key="inactive-test-001",
        )

    event_count = db.execute(
        select(func.count())
        .select_from(UsageEvent)
        .where(
            UsageEvent.tenant_id == tenant.id
        )
    ).scalar_one()

    assert event_count == 0