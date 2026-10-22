"""
ShopFlow Kadan (Store Credit) Information Endpoints.
"""

from typing import Annotated
from uuid import UUID
from fastapi import APIRouter, Depends, Query

from app.core import permissions as perm_constants
from app.core.dependencies import require_any_permission
from app.integrations.shopflow.client import ShopFlowClient, get_shopflow_client
from app.integrations.shopflow.schemas import (
    CloudCustomerListResponse,
    CloudShopBillingSummary,
)
from app.models.cloud_user import CloudUser

router = APIRouter(prefix="/shops/{tenant_id}/kadan", tags=["ShopFlow - Kadan"])

ReadAuthDep = Annotated[
    CloudUser,
    Depends(require_any_permission(perm_constants.SHOPFLOW_READ, perm_constants.DASHBOARD_VIEW)),
]


@router.get("/summary", response_model=CloudShopBillingSummary)
async def get_shop_kadan_summary(
    tenant_id: UUID,
    _current_user: ReadAuthDep,
    client: Annotated[ShopFlowClient, Depends(get_shopflow_client)],
) -> CloudShopBillingSummary:
    """Retrieve store credit (kadan) totals via shop billing summary."""
    return await client.get_shop_billing_summary(tenant_id)


@router.get("/customers", response_model=CloudCustomerListResponse)
async def list_shop_kadan_customers(
    tenant_id: UUID,
    _current_user: ReadAuthDep,
    client: Annotated[ShopFlowClient, Depends(get_shopflow_client)],
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    search: str | None = Query(None),
) -> CloudCustomerListResponse:
    """List customers with active kadan credit balances."""
    return await client.list_shop_customers(
        tenant_id=tenant_id,
        limit=limit,
        offset=offset,
        search=search,
        has_kadan_balance=True,
    )
