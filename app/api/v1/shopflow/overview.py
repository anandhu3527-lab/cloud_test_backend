"""
ShopFlow Overview & Health API Endpoints.
"""

from typing import Annotated
from fastapi import APIRouter, Depends

from app.core import permissions as perm_constants
from app.core.dependencies import require_any_permission
from app.integrations.shopflow.client import ShopFlowClient, get_shopflow_client
from app.integrations.shopflow.schemas import (
    BillsOverviewMetrics,
    OverallDashboardMetrics,
    SubscriptionOverviewMetrics,
    SystemHealthResponse,
)
from app.models.cloud_user import CloudUser
from app.services.shopflow.overview_service import get_dashboard_overview_metrics

router = APIRouter(prefix="/overview", tags=["ShopFlow - Overview"])

ReadAuthDep = Annotated[
    CloudUser,
    Depends(require_any_permission(perm_constants.SHOPFLOW_READ, perm_constants.DASHBOARD_VIEW)),
]


@router.get("", response_model=OverallDashboardMetrics)
async def get_shopflow_overview(
    _current_user: ReadAuthDep,
    client: Annotated[ShopFlowClient, Depends(get_shopflow_client)],
) -> OverallDashboardMetrics:
    """Retrieve aggregate ShopFlow platform metrics for Cloud dashboard including ShopFlow subscription revenue."""
    return await get_dashboard_overview_metrics(client)


@router.get("/health", response_model=SystemHealthResponse)
async def get_shopflow_health(
    _current_user: ReadAuthDep,
    client: Annotated[ShopFlowClient, Depends(get_shopflow_client)],
) -> SystemHealthResponse:
    """Check ShopFlow internal system and database health."""
    return await client.get_overview_health()


@router.get("/subscriptions", response_model=SubscriptionOverviewMetrics)
async def get_shopflow_subscription_overview(
    _current_user: ReadAuthDep,
    client: Annotated[ShopFlowClient, Depends(get_shopflow_client)],
) -> SubscriptionOverviewMetrics:
    """Retrieve aggregate subscription metrics across all shops."""
    return await client.get_overview_subscriptions()


@router.get("/bills", response_model=BillsOverviewMetrics)
async def get_shopflow_bills_overview(
    _current_user: ReadAuthDep,
    client: Annotated[ShopFlowClient, Depends(get_shopflow_client)],
) -> BillsOverviewMetrics:
    """Retrieve aggregate billing metrics across all shops."""
    return await client.get_overview_bills()
