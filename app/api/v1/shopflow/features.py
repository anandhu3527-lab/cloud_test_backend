"""
ShopFlow Features and Capabilities Endpoints.
"""

from typing import Annotated
from uuid import UUID
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.core import permissions as perm_constants
from app.core.dependencies import require_any_permission
from app.integrations.shopflow.client import ShopFlowClient, get_shopflow_client
from app.models.cloud_user import CloudUser

router = APIRouter(prefix="/features", tags=["ShopFlow - Features"])

ReadAuthDep = Annotated[
    CloudUser,
    Depends(require_any_permission(perm_constants.SHOPFLOW_READ, perm_constants.DASHBOARD_VIEW)),
]


class ShopFlowCapabilitiesResponse(BaseModel):
    supported_plans: list[str]
    supported_activation_statuses: list[str]
    features: dict[str, bool]


@router.get("", response_model=ShopFlowCapabilitiesResponse)
async def get_shopflow_capabilities(
    _current_user: ReadAuthDep,
) -> ShopFlowCapabilitiesResponse:
    """Retrieve verified capabilities and supported feature matrix for ShopFlow integration."""
    return ShopFlowCapabilitiesResponse(
        supported_plans=["SHOPFLOW", "TRIAL"],
        supported_activation_statuses=["ACTIVE"],
        features={
            "shops_management": True,
            "user_management": True,
            "product_inventory": True,
            "billing_and_bills": True,
            "cross_shop_bills": True,
            "subscription_management": True,
            "subscription_activation": True,
            "subscription_history": True,
            "audit_logs": True,
            "usage_metrics": True,
            "kadan_credit": True,
            "support_ticketing": False,  # Not supported upstream yet
        },
    )
