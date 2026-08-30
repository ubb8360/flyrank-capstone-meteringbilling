import hashlib

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Tenant
from app.repositories.tenant_repo import get_tenant_by_api_key_hash


def hash_api_key(api_key: str) -> str:
    return hashlib.sha256(
        api_key.encode("utf-8")
    ).hexdigest()


def get_current_tenant(
    x_api_key: str | None = Header(
        default=None,
        alias="X-API-Key"
    ),
    db: Session = Depends(get_db),
) -> Tenant:

    if not x_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key is required"
        )

    api_key_hash = hash_api_key(x_api_key)

    tenant = get_tenant_by_api_key_hash(
        db,
        api_key_hash
    )

    if tenant is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key"
        )

    return tenant