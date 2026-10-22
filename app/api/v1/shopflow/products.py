"""
ShopFlow Products and Inventory Endpoints.
"""

from typing import Annotated
from uuid import UUID
from fastapi import APIRouter, Depends, Query

from app.core import permissions as perm_constants
from app.core.dependencies import require_any_permission
from app.integrations.shopflow.client import ShopFlowClient, get_shopflow_client
from app.integrations.shopflow.schemas import (
    CloudProductDetailResponse,
    CloudProductListResponse,
    CloudProductUsageResponse,
    CloudProductVariantItem,
    CloudStockSummaryResponse,
)
from app.models.cloud_user import CloudUser

router = APIRouter(prefix="/shops/{tenant_id}/products", tags=["ShopFlow - Products & Inventory"])

ReadAuthDep = Annotated[
    CloudUser,
    Depends(require_any_permission(perm_constants.SHOPFLOW_READ, perm_constants.DASHBOARD_VIEW)),
]


@router.get("", response_model=CloudProductListResponse)
async def list_shop_products(
    tenant_id: UUID,
    _current_user: ReadAuthDep,
    client: Annotated[ShopFlowClient, Depends(get_shopflow_client)],
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    status: str | None = Query(None),
    search: str | None = Query(None),
    low_stock_only: bool = Query(False),
) -> CloudProductListResponse:
    """List catalog products for a specific shop with optional filtering."""
    return await client.list_shop_products(
        tenant_id=tenant_id,
        limit=limit,
        offset=offset,
        status=status,
        search=search,
        low_stock_only=low_stock_only,
    )


@router.get("/stock/summary", response_model=CloudStockSummaryResponse)
async def get_shop_stock_summary(
    tenant_id: UUID,
    _current_user: ReadAuthDep,
    client: Annotated[ShopFlowClient, Depends(get_shopflow_client)],
) -> CloudStockSummaryResponse:
    """Retrieve aggregate stock metrics, low-stock counts, and total inventory value."""
    return await client.get_shop_stock_summary(tenant_id)


@router.get("/usage", response_model=CloudProductUsageResponse)
async def get_shop_product_usage(
    tenant_id: UUID,
    _current_user: ReadAuthDep,
    client: Annotated[ShopFlowClient, Depends(get_shopflow_client)],
) -> CloudProductUsageResponse:
    """Retrieve catalog utilization metrics and top-selling products for a shop."""
    return await client.get_shop_product_usage(tenant_id)


@router.get("/{product_id}", response_model=CloudProductDetailResponse)
async def get_shop_product_details(
    tenant_id: UUID,
    product_id: UUID,
    _current_user: ReadAuthDep,
    client: Annotated[ShopFlowClient, Depends(get_shopflow_client)],
) -> CloudProductDetailResponse:
    """Retrieve full details of a product including its variants."""
    return await client.get_shop_product(tenant_id, product_id)


@router.get("/{product_id}/variants", response_model=list[CloudProductVariantItem])
async def get_shop_product_variants(
    tenant_id: UUID,
    product_id: UUID,
    _current_user: ReadAuthDep,
    client: Annotated[ShopFlowClient, Depends(get_shopflow_client)],
) -> list[CloudProductVariantItem]:
    """Retrieve all SKU variants associated with a product."""
    return await client.get_shop_product_variants(tenant_id, product_id)
