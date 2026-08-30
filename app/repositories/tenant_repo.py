from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Tenant


def get_tenant_by_api_key_hash(
    db: Session,
    api_key_hash: str
) -> Tenant | None:

    result = db.execute(
        select(Tenant).where(
            Tenant.api_key_hash == api_key_hash
        )
    )

    return result.scalar_one_or_none()