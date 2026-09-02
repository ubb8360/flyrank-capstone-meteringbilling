import hashlib
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete

from app.database import SessionLocal
from app.main import app
from app.models import Plan, Subscription, Tenant, UsageEvent
from app.services.meter_service import (
    record_ai_tokens,
    record_api_call,
)


client = TestClient(app)


@pytest.fixture
def usage_test_account():
    db = SessionLocal()

    suffix = uuid.uuid4().hex[:8]
    plan_id = 10000 + (uuid.uuid4().int % 1000000000)

    plan = Plan(
        id=plan_id,
        name=f"usage-test-plan-{suffix}",
        api_call_limit=10,
        ai_token_limit=5000,
    )

    api_key = f"usage-test-key-{suffix}"
    api_key_hash = hashlib.sha256(
        api_key.encode("utf-8")
    ).hexdigest()

    tenant = Tenant(
        id=uuid.uuid4(),
        name=f"Usage Test Tenant {suffix}",
        api_key_hash=api_key_hash,
    )

    other_api_key = f"other-test-key-{suffix}"
    other_api_key_hash = hashlib.sha256(
        other_api_key.encode("utf-8")
    ).hexdigest()

    other_tenant = Tenant(
        id=uuid.uuid4(),
        name=f"Other Test Tenant {suffix}",
        api_key_hash=other_api_key_hash,
    )

    db.add_all([
        plan,
        tenant,
        other_tenant,
    ])

    db.flush()

    subscription = Subscription(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        plan_id=plan.id,
        status="active",
    )

    other_subscription = Subscription(
        id=uuid.uuid4(),
        tenant_id=other_tenant.id,
        plan_id=plan.id,
        status="active",
    )

    db.add_all([
        subscription,
        other_subscription,
    ])

    db.commit()

    try:
        yield (
            db,
            tenant,
            other_tenant,
            plan,
            api_key,
        )

    finally:
        db.rollback()

        tenant_ids = [
            tenant.id,
            other_tenant.id,
        ]

        db.execute(
            delete(UsageEvent).where(
                UsageEvent.tenant_id.in_(tenant_ids)
            )
        )

        db.execute(
            delete(Subscription).where(
                Subscription.tenant_id.in_(tenant_ids)
            )
        )

        db.execute(
            delete(Tenant).where(
                Tenant.id.in_(tenant_ids)
            )
        )

        db.execute(
            delete(Plan).where(
                Plan.id == plan.id
            )
        )

        db.commit()
        db.close()


def test_usage_summary_rolls_up_usage_and_cost(
    usage_test_account
):
    db, tenant, _, plan, api_key = usage_test_account

    record_api_call(
        db=db,
        tenant=tenant,
        idempotency_key="usage-api-001",
    )

    record_api_call(
        db=db,
        tenant=tenant,
        idempotency_key="usage-api-002",
    )

    record_ai_tokens(
        db=db,
        tenant=tenant,
        idempotency_key="usage-ai-001",
        input_tokens=300,
        cached_input_tokens=100,
        output_tokens=200,
        reasoning_tokens=50,
    )

    response = client.get(
        "/usage",
        headers={
            "X-API-Key": api_key
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["tenant_id"] == str(tenant.id)
    assert data["plan"] == plan.name
    assert data["subscription_status"] == "active"

    assert data["api_calls"] == {
        "used": 2,
        "limit": 10,
    }

    assert data["ai_tokens"] == {
        "used": 650,
        "limit": 5000,
    }

    # 2 API calls = 200 microUSD
    # AI token event = 718 microUSD
    assert data["total_cost_microusd"] == 918


def test_usage_summary_is_tenant_isolated(
    usage_test_account
):
    (
        db,
        tenant,
        other_tenant,
        _,
        api_key,
    ) = usage_test_account

    record_api_call(
        db=db,
        tenant=tenant,
        idempotency_key="tenant-one-api",
    )

    record_api_call(
        db=db,
        tenant=other_tenant,
        idempotency_key="tenant-two-api-001",
    )

    record_api_call(
        db=db,
        tenant=other_tenant,
        idempotency_key="tenant-two-api-002",
    )

    response = client.get(
        "/usage",
        headers={
            "X-API-Key": api_key
        },
    )

    assert response.status_code == 200

    data = response.json()

    # The other tenant's two calls must not appear here.
    assert data["api_calls"]["used"] == 1
    assert data["total_cost_microusd"] == 100


def test_usage_requires_api_key():
    response = client.get("/usage")

    assert response.status_code == 401