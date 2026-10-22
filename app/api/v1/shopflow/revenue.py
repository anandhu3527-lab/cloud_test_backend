"""
ShopFlow Platform Revenue Endpoints.
"""

from typing import Annotated
from fastapi import APIRouter, Depends

from app.core import permissions as perm_constants
from app.core.dependencies import require_any_permission
from app.integrations.shopflow.client import ShopFlowClient, get_shopflow_client
from app.integrations.shopflow.schemas import BillsOverviewMetrics
from app.models.cloud_user import CloudUser

router = APIRouter(prefix="/revenue", tags=["ShopFlow - Revenue"])

ReadAuthDep = Annotated[
    CloudUser,
    Depends(require_any_permission(perm_constants.SHOPFLOW_READ, perm_constants.DASHBOARD_VIEW)),
]


@router.get("/summary", response_model=BillsOverviewMetrics)
async def get_revenue_summary(
    _current_user: ReadAuthDep,
    client: Annotated[ShopFlowClient, Depends(get_shopflow_client)],
) -> BillsOverviewMetrics:
    """Retrieve aggregate platform revenue metrics across all registered shops."""
    return await client.get_overview_bills()
