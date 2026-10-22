"""
ShopFlow Shop Alerts Endpoints.
"""

from typing import Annotated, Any
from uuid import UUID
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.core import permissions as perm_constants
from app.core.dependencies import require_any_permission
from app.integrations.shopflow.client import ShopFlowClient, get_shopflow_client
from app.models.cloud_user import CloudUser

router = APIRouter(prefix="/shops/{tenant_id}/alerts", tags=["ShopFlow - Alerts"])

ReadAuthDep = Annotated[
    CloudUser,
    Depends(require_any_permission(perm_constants.SHOPFLOW_READ, perm_constants.DASHBOARD_VIEW)),
]


class ShopAlertItem(BaseModel):
    severity: str
    code: str
    message: str


class ShopAlertsResponse(BaseModel):
    tenant_id: UUID
    alerts: list[ShopAlertItem]


@router.get("", response_model=ShopAlertsResponse)
async def get_shop_alerts(
    tenant_id: UUID,
    _current_user: ReadAuthDep,
    client: Annotated[ShopFlowClient, Depends(get_shopflow_client)],
) -> ShopAlertsResponse:
    """Retrieve operational alerts for a shop based on stock and subscription health."""
    alerts: list[ShopAlertItem] = []
    
    # Check shop stock summary
    try:
        stock = await client.get_shop_stock_summary(tenant_id)
        if stock.low_stock_variants_count > 0:
            alerts.append(
                ShopAlertItem(
                    severity="warning",
                    code="LOW_STOCK",
                    message=f"{stock.low_stock_variants_count} variant(s) are at or below low stock threshold.",
                )
            )
        if stock.out_of_stock_variants_count > 0:
            alerts.append(
                ShopAlertItem(
                    severity="critical",
                    code="OUT_OF_STOCK",
                    message=f"{stock.out_of_stock_variants_count} variant(s) are completely out of stock.",
                )
            )
    except Exception:
        pass

    # Check shop subscription
    try:
        sub = await client.get_shop_subscription(tenant_id)
        if sub.status != "ACTIVE":
            alerts.append(
                ShopAlertItem(
                    severity="critical",
                    code="SUBSCRIPTION_NOT_ACTIVE",
                    message=f"Shop subscription status is currently '{sub.status}'.",
                )
            )
    except Exception:
        alerts.append(
            ShopAlertItem(
                severity="warning",
                code="SUBSCRIPTION_MISSING",
                message="Shop does not have an active subscription configuration.",
            )
        )

    return ShopAlertsResponse(tenant_id=tenant_id, alerts=alerts)
