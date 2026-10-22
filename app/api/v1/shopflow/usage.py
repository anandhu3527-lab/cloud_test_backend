"""
ShopFlow Shop Usage Metrics Endpoints.
"""

from typing import Annotated
from uuid import UUID
from fastapi import APIRouter, Depends

from app.core import permissions as perm_constants
from app.core.dependencies import require_any_permission
from app.integrations.shopflow.client import ShopFlowClient, get_shopflow_client
from app.integrations.shopflow.schemas import CloudShopUsageResponse
from app.models.cloud_user import CloudUser

router = APIRouter(prefix="/shops/{tenant_id}/usage", tags=["ShopFlow - Usage"])

ReadAuthDep = Annotated[
    CloudUser,
    Depends(require_any_permission(perm_constants.SHOPFLOW_READ, perm_constants.DASHBOARD_VIEW)),
]


@router.get("", response_model=CloudShopUsageResponse)
async def get_shop_usage(
    tenant_id: UUID,
    _current_user: ReadAuthDep,
    client: Annotated[ShopFlowClient, Depends(get_shopflow_client)],
) -> CloudShopUsageResponse:
    """Retrieve cumulative resource usage metrics (bills, products, users, active days) for a shop."""
    return await client.get_shop_usage(tenant_id)
