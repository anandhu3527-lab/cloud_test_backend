"""
ShopFlow Customer Management Endpoints.
"""

from typing import Annotated
from uuid import UUID
from fastapi import APIRouter, Depends, Query

from app.core import permissions as perm_constants
from app.core.dependencies import require_any_permission
from app.integrations.shopflow.client import ShopFlowClient, get_shopflow_client
from app.integrations.shopflow.schemas import CloudCustomerListResponse
from app.models.cloud_user import CloudUser

router = APIRouter(prefix="/shops/{tenant_id}/customers", tags=["ShopFlow - Customers"])

ReadAuthDep = Annotated[
    CloudUser,
    Depends(require_any_permission(perm_constants.SHOPFLOW_READ, perm_constants.DASHBOARD_VIEW)),
]


@router.get("", response_model=CloudCustomerListResponse)
async def list_shop_customers(
    tenant_id: UUID,
    _current_user: ReadAuthDep,
    client: Annotated[ShopFlowClient, Depends(get_shopflow_client)],
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    search: str | None = Query(None),
    has_kadan_balance: bool | None = Query(None),
) -> CloudCustomerListResponse:
    """List customer records for a shop with search and kadan balance filtering."""
    return await client.list_shop_customers(
        tenant_id=tenant_id,
        limit=limit,
        offset=offset,
        search=search,
        has_kadan_balance=has_kadan_balance,
    )
