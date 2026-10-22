"""
ShopFlow Shop User Management Endpoints.
"""

from typing import Annotated
from uuid import UUID
from fastapi import APIRouter, Depends, Query

from app.core import permissions as perm_constants
from app.core.dependencies import require_any_permission, require_permission
from app.integrations.shopflow.client import ShopFlowClient, get_shopflow_client
from app.integrations.shopflow.schemas import (
    CloudShopActivityResponse,
    CloudUserAccessResetRequest,
    CloudUserAccessResetResponse,
    CloudUserDetailResponse,
    CloudUserListResponse,
    CloudUserStatusUpdateRequest,
    CloudUserStatusUpdateResponse,
)
from app.models.cloud_user import CloudUser

router = APIRouter(prefix="/shops/{tenant_id}/users", tags=["ShopFlow - Shop Users"])

ReadAuthDep = Annotated[
    CloudUser,
    Depends(require_any_permission(perm_constants.SHOPFLOW_READ, perm_constants.DASHBOARD_VIEW)),
]
ManageAuthDep = Annotated[
    CloudUser,
    Depends(require_permission(perm_constants.SHOPFLOW_MANAGE)),
]


@router.get("", response_model=CloudUserListResponse)
async def list_shop_users(
    tenant_id: UUID,
    _current_user: ReadAuthDep,
    client: Annotated[ShopFlowClient, Depends(get_shopflow_client)],
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    status: str | None = Query(None),
) -> CloudUserListResponse:
    """List all user accounts belonging to a given shop."""
    return await client.list_shop_users(tenant_id, limit=limit, offset=offset, status=status)


@router.get("/{user_id}", response_model=CloudUserDetailResponse)
async def get_shop_user_details(
    tenant_id: UUID,
    user_id: UUID,
    _current_user: ReadAuthDep,
    client: Annotated[ShopFlowClient, Depends(get_shopflow_client)],
) -> CloudUserDetailResponse:
    """Retrieve full details of a shop user."""
    return await client.get_shop_user(tenant_id, user_id)


@router.patch("/{user_id}/status", response_model=CloudUserStatusUpdateResponse)
async def update_shop_user_status(
    tenant_id: UUID,
    user_id: UUID,
    payload: CloudUserStatusUpdateRequest,
    _current_user: ManageAuthDep,
    client: Annotated[ShopFlowClient, Depends(get_shopflow_client)],
) -> CloudUserStatusUpdateResponse:
    """Change operational status of a shop user (ACTIVE, INACTIVE, SUSPENDED)."""
    return await client.update_shop_user_status(tenant_id, user_id, payload)


@router.post("/{user_id}/access-reset", response_model=CloudUserAccessResetResponse)
async def reset_shop_user_access(
    tenant_id: UUID,
    user_id: UUID,
    payload: CloudUserAccessResetRequest,
    _current_user: ManageAuthDep,
    client: Annotated[ShopFlowClient, Depends(get_shopflow_client)],
) -> CloudUserAccessResetResponse:
    """Trigger controlled password/access reset workflow for a shop user."""
    return await client.reset_shop_user_access(tenant_id, user_id, payload)


@router.get("/{user_id}/activity", response_model=CloudShopActivityResponse)
async def get_shop_user_activity(
    tenant_id: UUID,
    user_id: UUID,
    _current_user: ReadAuthDep,
    client: Annotated[ShopFlowClient, Depends(get_shopflow_client)],
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> CloudShopActivityResponse:
    """Retrieve audit events performed by or affecting this shop user."""
    return await client.get_shop_user_activity(tenant_id, user_id, limit=limit, offset=offset)
