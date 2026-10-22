"""
ShopFlow Health Check Endpoint.
"""

from typing import Annotated
from fastapi import APIRouter, Depends

from app.core import permissions as perm_constants
from app.core.dependencies import require_any_permission
from app.integrations.shopflow.client import ShopFlowClient, get_shopflow_client
from app.integrations.shopflow.schemas import SystemHealthResponse
from app.models.cloud_user import CloudUser

router = APIRouter(prefix="/health", tags=["ShopFlow - Health"])


@router.get("", response_model=SystemHealthResponse)
async def check_shopflow_service_health(
    _current_user: Annotated[
        CloudUser,
        Depends(require_any_permission(perm_constants.SHOPFLOW_READ, perm_constants.DASHBOARD_VIEW)),
    ],
    client: Annotated[ShopFlowClient, Depends(get_shopflow_client)],
) -> SystemHealthResponse:
    """Check ShopFlow service and database connectivity from CRYVEX Cloud."""
    return await client.get_overview_health()
