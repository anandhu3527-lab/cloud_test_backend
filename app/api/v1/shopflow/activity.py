"""
ShopFlow Activity History Endpoints.
"""

from typing import Annotated
from uuid import UUID
from fastapi import APIRouter, Depends, Query

from app.core import permissions as perm_constants
from app.core.dependencies import require_any_permission
from app.integrations.shopflow.client import ShopFlowClient, get_shopflow_client
from app.integrations.shopflow.schemas import CloudShopActivityResponse
from app.models.cloud_user import CloudUser

router = APIRouter(prefix="/activity", tags=["ShopFlow - Activity"])

ReadAuthDep = Annotated[
    CloudUser,
    Depends(require_any_permission(perm_constants.SHOPFLOW_READ, perm_constants.DASHBOARD_VIEW)),
]


@router.get("/shops/{tenant_id}", response_model=CloudShopActivityResponse)
async def get_shop_activity(
    tenant_id: UUID,
    _current_user: ReadAuthDep,
    client: Annotated[ShopFlowClient, Depends(get_shopflow_client)],
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> CloudShopActivityResponse:
    """Retrieve activity log stream for a specific shop."""
    return await client.get_shop_activity(tenant_id, limit=limit, offset=offset)


@router.get("/shops/{tenant_id}/users/{user_id}", response_model=CloudShopActivityResponse)
async def get_user_activity(
    tenant_id: UUID,
    user_id: UUID,
    _current_user: ReadAuthDep,
    client: Annotated[ShopFlowClient, Depends(get_shopflow_client)],
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> CloudShopActivityResponse:
    """Retrieve activity stream associated with a specific user in a shop."""
    return await client.get_shop_user_activity(tenant_id, user_id, limit=limit, offset=offset)
