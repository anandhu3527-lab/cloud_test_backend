"""
ShopFlow Shop Management API Endpoints.
"""

from typing import Annotated
from uuid import UUID
from fastapi import APIRouter, Depends, Query

from app.core import permissions as perm_constants
from app.core.dependencies import require_any_permission, require_permission
from app.integrations.shopflow.client import ShopFlowClient, get_shopflow_client
from app.integrations.shopflow.schemas import (
    CloudShopActivityResponse,
    CloudShopDetailResponse,
    CloudShopKPIs,
    CloudShopListResponse,
    CloudShopStatusUpdateRequest,
    CloudShopStatusUpdateResponse,
    ShopsWithoutSubscriptionResponse,
)
from app.models.cloud_user import CloudUser

router = APIRouter(prefix="/shops", tags=["ShopFlow - Shops"])

ReadAuthDep = Annotated[
    CloudUser,
    Depends(require_any_permission(perm_constants.SHOPFLOW_READ, perm_constants.DASHBOARD_VIEW)),
]
ManageAuthDep = Annotated[
    CloudUser,
    Depends(require_permission(perm_constants.SHOPFLOW_MANAGE)),
]


@router.get("", response_model=CloudShopListResponse)
async def list_shops(
    _current_user: ReadAuthDep,
    client: Annotated[ShopFlowClient, Depends(get_shopflow_client)],
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    status: str | None = Query(None),
    search: str | None = Query(None),
) -> CloudShopListResponse:
    """List shops with pagination and optional status or name filtering."""
    return await client.list_shops(limit=limit, offset=offset, status=status, search=search)


@router.get("/without-subscription", response_model=ShopsWithoutSubscriptionResponse)
async def list_shops_without_subscription(
    _current_user: ReadAuthDep,
    client: Annotated[ShopFlowClient, Depends(get_shopflow_client)],
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> ShopsWithoutSubscriptionResponse:
    """List shops that lack an active or complete subscription configuration."""
    return await client.list_shops_without_subscription(limit=limit, offset=offset)


@router.get("/{tenant_id}", response_model=CloudShopDetailResponse)
async def get_shop_details(
    tenant_id: UUID,
    _current_user: ReadAuthDep,
    client: Annotated[ShopFlowClient, Depends(get_shopflow_client)],
) -> CloudShopDetailResponse:
    """Retrieve full details of a specific shop."""
    return await client.get_shop(tenant_id)


@router.get("/{tenant_id}/overview", response_model=CloudShopKPIs)
async def get_shop_overview(
    tenant_id: UUID,
    _current_user: ReadAuthDep,
    client: Annotated[ShopFlowClient, Depends(get_shopflow_client)],
) -> CloudShopKPIs:
    """Retrieve key performance indicators and usage summaries for a specific shop."""
    return await client.get_shop_overview(tenant_id)


@router.get("/{tenant_id}/activity", response_model=CloudShopActivityResponse)
async def get_shop_activity(
    tenant_id: UUID,
    _current_user: ReadAuthDep,
    client: Annotated[ShopFlowClient, Depends(get_shopflow_client)],
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> CloudShopActivityResponse:
    """Retrieve audit activity events for a specific shop."""
    return await client.get_shop_activity(tenant_id, limit=limit, offset=offset)


@router.patch("/{tenant_id}/status", response_model=CloudShopStatusUpdateResponse)
async def update_shop_status(
    tenant_id: UUID,
    payload: CloudShopStatusUpdateRequest,
    _current_user: ManageAuthDep,
    client: Annotated[ShopFlowClient, Depends(get_shopflow_client)],
) -> CloudShopStatusUpdateResponse:
    """Update operational status of a shop (ACTIVE, SUSPENDED, INACTIVE)."""
    return await client.update_shop_status(tenant_id, payload)
