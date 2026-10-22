"""
ShopFlow Shop Support Integration Endpoints.
"""

from typing import Annotated
from uuid import UUID
from fastapi import APIRouter, Depends

from app.core import permissions as perm_constants
from app.core.dependencies import require_any_permission
from app.integrations.shopflow.client import ShopFlowClient, get_shopflow_client
from app.integrations.shopflow.schemas import CloudSupportResponse
from app.models.cloud_user import CloudUser

router = APIRouter(prefix="/shops/{tenant_id}/support", tags=["ShopFlow - Support"])

ReadAuthDep = Annotated[
    CloudUser,
    Depends(require_any_permission(perm_constants.SHOPFLOW_READ, perm_constants.DASHBOARD_VIEW)),
]


@router.get("", response_model=CloudSupportResponse)
async def get_shop_support(
    tenant_id: UUID,
    _current_user: ReadAuthDep,
    client: Annotated[ShopFlowClient, Depends(get_shopflow_client)],
) -> CloudSupportResponse:
    """Retrieve support integration status for a shop."""
    return await client.get_shop_support(tenant_id)
