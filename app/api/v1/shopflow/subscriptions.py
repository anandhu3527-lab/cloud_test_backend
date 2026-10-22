"""
ShopFlow Subscription Management API Endpoints.
"""

from typing import Annotated
from uuid import UUID
from fastapi import APIRouter, Depends, Query

from app.core import permissions as perm_constants
from app.core.dependencies import require_any_permission, require_permission
from app.integrations.shopflow.client import ShopFlowClient, get_shopflow_client
from app.integrations.shopflow.schemas import (
    CloudShopSubscriptionListResponse,
    CloudSubscriptionActionRequest,
    CloudSubscriptionActivationRequest,
    CloudSubscriptionActivationResponse,
    CloudSubscriptionChangeRequest,
    CloudSubscriptionDetail,
    CloudSubscriptionHistoryResponse,
    CloudSubscriptionOperationResponse,
    ShopsWithoutSubscriptionResponse,
)
from app.models.cloud_user import CloudUser

router = APIRouter(tags=["ShopFlow - Subscriptions"])

ReadAuthDep = Annotated[
    CloudUser,
    Depends(require_any_permission(perm_constants.SHOPFLOW_READ, perm_constants.DASHBOARD_VIEW)),
]
ManageSubAuthDep = Annotated[
    CloudUser,
    Depends(
        require_any_permission(
            perm_constants.SHOPFLOW_MANAGE,
            perm_constants.SHOPFLOW_SUBSCRIPTION_MANAGE,
        )
    ),
]


# ============================================================
# CROSS-SHOP SUBSCRIPTION ENDPOINTS
# ============================================================

@router.get("/subscriptions", response_model=CloudShopSubscriptionListResponse)
async def list_all_subscriptions(
    _current_user: ReadAuthDep,
    client: Annotated[ShopFlowClient, Depends(get_shopflow_client)],
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    plan: str | None = Query(None),
    status: str | None = Query(None),
) -> CloudShopSubscriptionListResponse:
    """List all shop subscriptions joined with shop details for platform administration."""
    return await client.list_subscriptions(limit=limit, offset=offset, plan=plan, status=status)


@router.get("/subscriptions/without-subscription", response_model=ShopsWithoutSubscriptionResponse)
async def list_shops_missing_subscription(
    _current_user: ReadAuthDep,
    client: Annotated[ShopFlowClient, Depends(get_shopflow_client)],
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> ShopsWithoutSubscriptionResponse:
    """Convenience alias: List shops without an active subscription record."""
    return await client.list_shops_without_subscription(limit=limit, offset=offset)


@router.get("/subscriptions/{subscription_id}", response_model=CloudSubscriptionDetail)
async def get_subscription_by_id(
    subscription_id: UUID,
    _current_user: ReadAuthDep,
    client: Annotated[ShopFlowClient, Depends(get_shopflow_client)],
) -> CloudSubscriptionDetail:
    """Retrieve details of a specific subscription by its unique subscription ID."""
    return await client.get_subscription_by_id(subscription_id)


# ============================================================
# SHOP-SPECIFIC SUBSCRIPTION ENDPOINTS
# ============================================================

@router.get("/shops/{tenant_id}/subscription", response_model=CloudSubscriptionDetail)
async def get_shop_current_subscription(
    tenant_id: UUID,
    _current_user: ReadAuthDep,
    client: Annotated[ShopFlowClient, Depends(get_shopflow_client)],
) -> CloudSubscriptionDetail:
    """Retrieve the active or most recent subscription configuration for a shop."""
    return await client.get_shop_subscription(tenant_id)


@router.get("/shops/{tenant_id}/subscription/history", response_model=CloudSubscriptionHistoryResponse)
async def get_shop_subscription_history(
    tenant_id: UUID,
    _current_user: ReadAuthDep,
    client: Annotated[ShopFlowClient, Depends(get_shopflow_client)],
) -> CloudSubscriptionHistoryResponse:
    """Retrieve subscription history and lifecycle audit events for a shop."""
    return await client.get_shop_subscription_history(tenant_id)


@router.post(
    "/shops/{tenant_id}/subscription/activate",
    response_model=CloudSubscriptionActivationResponse,
)
async def activate_shop_subscription(
    tenant_id: UUID,
    payload: CloudSubscriptionActivationRequest,
    _current_user: ManageSubAuthDep,
    client: Annotated[ShopFlowClient, Depends(get_shopflow_client)],
) -> CloudSubscriptionActivationResponse:
    """
    Administratively activate a subscription for a shop.
    Security: Tenant ID is always strictly derived from the route context.
    """
    return await client.activate_shop_subscription(tenant_id, payload)


@router.post(
    "/shops/{tenant_id}/subscription/upgrade",
    response_model=CloudSubscriptionOperationResponse,
)
async def upgrade_shop_subscription(
    tenant_id: UUID,
    payload: CloudSubscriptionChangeRequest,
    _current_user: ManageSubAuthDep,
    client: Annotated[ShopFlowClient, Depends(get_shopflow_client)],
) -> CloudSubscriptionOperationResponse:
    """Upgrade an active shop subscription to a higher tier plan."""
    return await client.upgrade_shop_subscription(tenant_id, payload)


@router.post(
    "/shops/{tenant_id}/subscription/downgrade",
    response_model=CloudSubscriptionOperationResponse,
)
async def downgrade_shop_subscription(
    tenant_id: UUID,
    payload: CloudSubscriptionChangeRequest,
    _current_user: ManageSubAuthDep,
    client: Annotated[ShopFlowClient, Depends(get_shopflow_client)],
) -> CloudSubscriptionOperationResponse:
    """Downgrade an active shop subscription."""
    return await client.downgrade_shop_subscription(tenant_id, payload)


@router.post(
    "/shops/{tenant_id}/subscription/suspend",
    response_model=CloudSubscriptionOperationResponse,
)
async def suspend_shop_subscription(
    tenant_id: UUID,
    payload: CloudSubscriptionActionRequest,
    _current_user: ManageSubAuthDep,
    client: Annotated[ShopFlowClient, Depends(get_shopflow_client)],
) -> CloudSubscriptionOperationResponse:
    """Temporarily suspend a shop's subscription."""
    return await client.suspend_shop_subscription(tenant_id, payload)


@router.post(
    "/shops/{tenant_id}/subscription/cancel",
    response_model=CloudSubscriptionOperationResponse,
)
async def cancel_shop_subscription(
    tenant_id: UUID,
    payload: CloudSubscriptionActionRequest,
    _current_user: ManageSubAuthDep,
    client: Annotated[ShopFlowClient, Depends(get_shopflow_client)],
) -> CloudSubscriptionOperationResponse:
    """Cancel a shop's subscription."""
    return await client.cancel_shop_subscription(tenant_id, payload)
