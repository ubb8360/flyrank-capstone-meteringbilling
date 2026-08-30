import uuid

from sqlalchemy import (
    BigInteger,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base


class Tenant(Base):
    __tablename__ = "tenants"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(150), nullable=False)
    api_key_hash = Column(String(255), nullable=False, unique=True)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now()
    )


class Plan(Base):
    __tablename__ = "plans"

    id = Column(Integer, primary_key=True)
    name = Column(String(50), nullable=False, unique=True)
    api_call_limit = Column(Integer, nullable=False)
    ai_token_limit = Column(BigInteger, nullable=False)


class Subscription(Base):
    __tablename__ = "subscriptions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    tenant_id = Column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id"),
        nullable=False,
        unique=True
    )

    plan_id = Column(
        Integer,
        ForeignKey("plans.id"),
        nullable=False
    )

    status = Column(String(50), nullable=False)

    stripe_customer_id = Column(
        String(255),
        nullable=True,
        unique=True
    )

    stripe_subscription_id = Column(
        String(255),
        nullable=True,
        unique=True
    )

    current_period_start = Column(
        DateTime(timezone=True),
        nullable=True
    )

    current_period_end = Column(
        DateTime(timezone=True),
        nullable=True
    )

    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now()
    )


class UsageEvent(Base):
    __tablename__ = "usage_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    tenant_id = Column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id"),
        nullable=False
    )

    usage_type = Column(String(30), nullable=False)
    quantity = Column(BigInteger, nullable=False)

    input_tokens = Column(BigInteger, nullable=True)
    cached_input_tokens = Column(BigInteger, nullable=True)
    output_tokens = Column(BigInteger, nullable=True)
    reasoning_tokens = Column(BigInteger, nullable=True)

    cost_microusd = Column(
        BigInteger,
        nullable=False
    )

    idempotency_key = Column(
        String(255),
        nullable=False
    )

    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now()
    )

    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "idempotency_key",
            name="uq_usage_events_tenant_idempotency_key"
        ),
        Index(
            "ix_usage_events_tenant_created_at",
            "tenant_id",
            "created_at"
        ),
    )


class StripeEvent(Base):
    __tablename__ = "stripe_events"

    id = Column(String(255), primary_key=True)
    event_type = Column(String(100), nullable=False)

    processed_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now()
    )