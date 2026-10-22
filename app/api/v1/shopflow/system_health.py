"""
ShopFlow System Health Router.
"""

from typing import Annotated
from fastapi import APIRouter, Depends

from app.core import permissions as perm_constants
from app.core.dependencies import require_any_permission
from app.integrations.shopflow.client import ShopFlowClient, get_shopflow_client
from app.integrations.shopflow.schemas import SystemHealthResponse
from app.models.cloud_user import CloudUser

router = APIRouter(prefix="/system-health", tags=["ShopFlow - System Health"])


@router.get("", response_model=SystemHealthResponse)
async def get_system_health(
    _current_user: Annotated[
        CloudUser,
        Depends(require_any_permission(perm_constants.SHOPFLOW_READ, perm_constants.DASHBOARD_VIEW)),
    ],
    client: Annotated[ShopFlowClient, Depends(get_shopflow_client)],
) -> SystemHealthResponse:
    """Detailed health check for ShopFlow backend components."""
    return await client.get_overview_health()
