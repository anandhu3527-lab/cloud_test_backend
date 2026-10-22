"""
ShopFlow Shop Audit Log Endpoints.
"""

from typing import Annotated
from uuid import UUID
from fastapi import APIRouter, Depends, Query

from app.core import permissions as perm_constants
from app.core.dependencies import require_any_permission
from app.integrations.shopflow.client import ShopFlowClient, get_shopflow_client
from app.integrations.shopflow.schemas import CloudAuditLogListResponse
from app.models.cloud_user import CloudUser

router = APIRouter(prefix="/shops/{tenant_id}/audit-logs", tags=["ShopFlow - Audit Logs"])

ReadAuthDep = Annotated[
    CloudUser,
    Depends(require_any_permission(perm_constants.SHOPFLOW_READ, perm_constants.DASHBOARD_VIEW)),
]


@router.get("", response_model=CloudAuditLogListResponse)
async def list_shop_audit_logs(
    tenant_id: UUID,
    _current_user: ReadAuthDep,
    client: Annotated[ShopFlowClient, Depends(get_shopflow_client)],
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    action: str | None = Query(None),
    user_id: UUID | None = Query(None),
) -> CloudAuditLogListResponse:
    """Retrieve audit log events for a shop with action and actor filtering."""
    return await client.list_shop_audit_logs(
        tenant_id=tenant_id,
        limit=limit,
        offset=offset,
        action=action,
        user_id=user_id,
    )
