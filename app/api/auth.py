from fastapi import APIRouter, Depends

from app.auth import get_current_tenant
from app.models import Tenant


router = APIRouter(
    prefix="/auth",
    tags=["auth"]
)


@router.get("/check")
def check_auth(
    tenant: Tenant = Depends(get_current_tenant)
):
    return {
        "authenticated": True,
        "tenant_id": str(tenant.id),
        "tenant_name": tenant.name
    }