"""
Integration and API tests for Cloud-facing ShopFlow endpoints.
Tests Cloud human user authentication, RBAC enforcement, and upstream request forwarding.
"""

from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock
import uuid
from httpx import AsyncClient
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import permissions as perm_constants
from app.core.security import get_password_hash
from app.integrations.shopflow.client import ShopFlowClient, get_shopflow_client
from app.integrations.shopflow.schemas import (
    CloudBillItemResponse,
    CloudBillListResponse,
    CloudCustomerListItem,
    CloudCustomerListResponse,
    CloudProductListItem,
    CloudProductListResponse,
    CloudShopDetailResponse,
    CloudShopListItem,
    CloudShopListResponse,
    CloudShopStatusUpdateResponse,
    CloudShopSubscriptionItem,
    CloudShopSubscriptionListResponse,
    CloudSubscriptionActivationResponse,
    CloudSubscriptionDetail,
    CloudSubscriptionOperationResponse,
    CloudUserAccessResetResponse,
    CloudUserDetailResponse,
    CloudUserListItem,
    CloudUserListResponse,
    CloudUserStatusUpdateResponse,
    OverallDashboardMetrics,
    PaginatedMeta,
    ShopWithoutSubscriptionItem,
    ShopsWithoutSubscriptionResponse,
    SystemHealthResponse,
)
from app.main import app
from app.models.cloud_permission import CloudPermission
from app.models.cloud_role import CloudRole
from app.models.cloud_user import CloudUser
from app.models.role_permission import CloudRolePermission


# ──────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────

@pytest.fixture
async def superuser(db_session: AsyncSession):
    role = CloudRole(name="SUPERUSER", description="Superuser role")
    db_session.add(role)

    user = CloudUser(
        email="admin@cryvex.com",
        password_hash=get_password_hash("AdminPass123!"),
        first_name="Admin",
        last_name="Super",
        is_active=True,
        is_email_verified=True,
    )
    user.roles.append(role)
    db_session.add(user)
    await db_session.commit()
    return user


@pytest.fixture
async def read_only_employee(db_session: AsyncSession):
    role = CloudRole(name="EMPLOYEE", description="Standard employee access")
    db_session.add(role)

    perm = CloudPermission(
        name=perm_constants.SHOPFLOW_READ,
        description="View ShopFlow data",
        resource="shopflow",
        action="read",
    )
    db_session.add(perm)
    await db_session.commit()
    await db_session.refresh(role)
    await db_session.refresh(perm)

    link = CloudRolePermission(role_id=role.id, permission_id=perm.id)
    db_session.add(link)

    user = CloudUser(
        email="employee@cryvex.com",
        password_hash=get_password_hash("EmployeePass123!"),
        first_name="Read",
        last_name="Employee",
        is_active=True,
        is_email_verified=True,
    )
    user.roles.append(role)
    db_session.add(user)
    await db_session.commit()
    return user


@pytest.fixture
async def no_perm_user(db_session: AsyncSession):
    role = CloudRole(name="NOROLE", description="No permissions")
    db_session.add(role)

    user = CloudUser(
        email="noperm@cryvex.com",
        password_hash=get_password_hash("NoPermPass123!"),
        first_name="No",
        last_name="Perm",
        is_active=True,
        is_email_verified=True,
    )
    user.roles.append(role)
    db_session.add(user)
    await db_session.commit()
    return user


async def get_token_for(client: AsyncClient, email: str, password: str) -> str:
    login_res = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert login_res.status_code == 200, f"Login failed: {login_res.text}"
    return login_res.json()["access_token"]


@pytest.fixture
async def unrelated_perm_user(db_session: AsyncSession):
    """User with permissions unrelated to shopflow:manage (e.g. employee:read)."""
    role = CloudRole(name="AUDITOR", description="Auditor with read permissions only")
    db_session.add(role)

    perm = CloudPermission(
        name=perm_constants.EMPLOYEE_READ,
        description="View employee details",
        resource="employee",
        action="read",
    )
    db_session.add(perm)
    await db_session.commit()
    await db_session.refresh(role)
    await db_session.refresh(perm)

    link = CloudRolePermission(role_id=role.id, permission_id=perm.id)
    db_session.add(link)

    user = CloudUser(
        email="unrelated@cryvex.com",
        password_hash=get_password_hash("UnrelatedPass123!"),
        first_name="Unrelated",
        last_name="Perm",
        is_active=True,
        is_email_verified=True,
    )
    user.roles.append(role)
    db_session.add(user)
    await db_session.commit()
    return user


# ──────────────────────────────────────────────
# Tests: Authentication & Authorization (RBAC)
# ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_unauthenticated_request_rejected(client: AsyncClient):
    res = await client.get("/api/v1/shopflow/overview")
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_unauthenticated_shop_status_update_rejected(client: AsyncClient):
    """Case 3: An unauthenticated request to update shop status is rejected."""
    tenant_id = uuid.uuid4()
    res = await client.patch(
        f"/api/v1/shopflow/shops/{tenant_id}/status",
        json={"status": "ACTIVE", "reason": "Attempt without credentials"},
    )
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_user_without_permission_rejected(client: AsyncClient, no_perm_user: CloudUser):
    token = await get_token_for(client, "noperm@cryvex.com", "NoPermPass123!")
    res = await client.get(
        "/api/v1/shopflow/overview",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_normal_user_without_permission_cannot_update_shop_status(client: AsyncClient, no_perm_user: CloudUser):
    """Case 2: A normal user without the required permission receives 403."""
    token = await get_token_for(client, "noperm@cryvex.com", "NoPermPass123!")
    tenant_id = uuid.uuid4()
    res = await client.patch(
        f"/api/v1/shopflow/shops/{tenant_id}/status",
        headers={"Authorization": f"Bearer {token}"},
        json={"status": "SUSPENDED", "reason": "No permission test"},
    )
    assert res.status_code == 403
    assert res.json().get("detail") == "Not enough permissions"


@pytest.mark.asyncio
async def test_user_with_unrelated_permission_cannot_update_shop_status(client: AsyncClient, unrelated_perm_user: CloudUser):
    """Case 4: A user with unrelated permissions cannot update shop status."""
    token = await get_token_for(client, "unrelated@cryvex.com", "UnrelatedPass123!")
    tenant_id = uuid.uuid4()
    res = await client.patch(
        f"/api/v1/shopflow/shops/{tenant_id}/status",
        headers={"Authorization": f"Bearer {token}"},
        json={"status": "SUSPENDED", "reason": "Unrelated permission test"},
    )
    assert res.status_code == 403
    assert res.json().get("detail") == "Not enough permissions"


@pytest.mark.asyncio
async def test_invalid_status_value_rejected(client: AsyncClient, superuser: CloudUser):
    """Case 5: Invalid status values are rejected with 422 validation error."""
    token = await get_token_for(client, "admin@cryvex.com", "AdminPass123!")
    tenant_id = uuid.uuid4()
    res = await client.patch(
        f"/api/v1/shopflow/shops/{tenant_id}/status",
        headers={"Authorization": f"Bearer {token}"},
        json={"status": "COMPLETELY_INVALID_STATUS", "reason": "Testing validation"},
    )
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_employee_can_access_read_routes(client: AsyncClient, read_only_employee: CloudUser):
    token = await get_token_for(client, "employee@cryvex.com", "EmployeePass123!")

    mock_client = AsyncMock(spec=ShopFlowClient)
    mock_client.get_overview.return_value = OverallDashboardMetrics(
        total_shops=5,
        active_shops=4,
        trial_shops=1,
        suspended_shops=0,
        expired_shops=0,
        new_shops_this_month=2,
        active_users=10,
        bills_generated_today=3,
        monthly_revenue=Decimal("15000.00"),
    )

    app.dependency_overrides[get_shopflow_client] = lambda: mock_client
    try:
        res = await client.get(
            "/api/v1/shopflow/overview",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res.status_code == 200
        data = res.json()
        assert data["total_shops"] == 5
        assert data["monthly_revenue"] == "15000.00"
    finally:
        app.dependency_overrides.pop(get_shopflow_client, None)


@pytest.mark.asyncio
async def test_employee_cannot_mutate_shop_status(client: AsyncClient, read_only_employee: CloudUser):
    token = await get_token_for(client, "employee@cryvex.com", "EmployeePass123!")
    tenant_id = uuid.uuid4()

    res = await client.patch(
        f"/api/v1/shopflow/shops/{tenant_id}/status",
        headers={"Authorization": f"Bearer {token}"},
        json={"status": "SUSPENDED", "reason": "Non-payment"},
    )
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_employee_cannot_activate_subscription(client: AsyncClient, read_only_employee: CloudUser):
    token = await get_token_for(client, "employee@cryvex.com", "EmployeePass123!")
    tenant_id = uuid.uuid4()

    res = await client.post(
        f"/api/v1/shopflow/shops/{tenant_id}/subscription/activate",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "plan": "SHOPFLOW",
            "status": "ACTIVE",
            "start_date": "2026-10-22T00:00:00Z",
            "end_date": "2027-10-22T00:00:00Z",
            "reason": "Admin activation test",
        },
    )
    assert res.status_code == 403



# ──────────────────────────────────────────────
# Tests: Superuser Operations & Forwarding
# ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_superuser_can_mutate_shop_status(client: AsyncClient, superuser: CloudUser):
    token = await get_token_for(client, "admin@cryvex.com", "AdminPass123!")
    tenant_id = uuid.uuid4()

    mock_client = AsyncMock(spec=ShopFlowClient)
    mock_client.update_shop_status.return_value = CloudShopStatusUpdateResponse(
        success=True,
        tenant_id=tenant_id,
        previous_status="ACTIVE",
        new_status="SUSPENDED",
        message="Shop status updated to SUSPENDED",
    )

    app.dependency_overrides[get_shopflow_client] = lambda: mock_client
    try:
        res = await client.patch(
            f"/api/v1/shopflow/shops/{tenant_id}/status",
            headers={"Authorization": f"Bearer {token}"},
            json={"status": "SUSPENDED", "reason": "Policy violation"},
        )
        assert res.status_code == 200
        data = res.json()
        assert data["success"] is True
        assert data["new_status"] == "SUSPENDED"
        mock_client.update_shop_status.assert_called_once()
    finally:
        app.dependency_overrides.pop(get_shopflow_client, None)


@pytest.mark.asyncio
async def test_subscription_activation_payload_forwarding(client: AsyncClient, superuser: CloudUser):
    token = await get_token_for(client, "admin@cryvex.com", "AdminPass123!")
    tenant_id = uuid.uuid4()
    sub_id = uuid.uuid4()
    start_dt = datetime(2026, 10, 22, 0, 0, 0, tzinfo=timezone.utc)
    end_dt = datetime(2027, 10, 22, 0, 0, 0, tzinfo=timezone.utc)

    mock_client = AsyncMock(spec=ShopFlowClient)
    mock_client.activate_shop_subscription.return_value = CloudSubscriptionActivationResponse(
        success=True,
        subscription_id=sub_id,
        tenant_id=tenant_id,
        plan="SHOPFLOW",
        status="ACTIVE",
        start_date=start_dt,
        end_date=end_dt,
        created_at=start_dt,
        updated_at=start_dt,
        message="Subscription activated successfully",
    )

    app.dependency_overrides[get_shopflow_client] = lambda: mock_client
    try:
        res = await client.post(
            f"/api/v1/shopflow/shops/{tenant_id}/subscription/activate",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "plan": "SHOPFLOW",
                "status": "ACTIVE",
                "start_date": "2026-10-22T00:00:00Z",
                "end_date": "2027-10-22T00:00:00Z",
                "reason": "Shop onboarded and plan activated by admin",
            },
        )
        assert res.status_code == 200
        data = res.json()
        assert data["success"] is True
        assert data["plan"] == "SHOPFLOW"
        assert data["subscription_id"] == str(sub_id)

        # Verify tenant_id in client call strictly matches route context
        called_tenant_id, called_payload = mock_client.activate_shop_subscription.call_args[0]
        assert called_tenant_id == tenant_id
        assert called_payload.plan == "SHOPFLOW"
        assert called_payload.reason == "Shop onboarded and plan activated by admin"
    finally:
        app.dependency_overrides.pop(get_shopflow_client, None)


@pytest.mark.asyncio
async def test_shops_without_subscription_listing(client: AsyncClient, read_only_employee: CloudUser):
    token = await get_token_for(client, "employee@cryvex.com", "EmployeePass123!")
    tenant_id = uuid.uuid4()
    now = datetime.now(timezone.utc)

    mock_client = AsyncMock(spec=ShopFlowClient)
    mock_client.list_shops_without_subscription.return_value = ShopsWithoutSubscriptionResponse(
        meta=PaginatedMeta(total=1, limit=50, offset=0),
        shops=[
            ShopWithoutSubscriptionItem(
                tenant_id=tenant_id,
                name="Test Shop",
                business_name="Test Enterprise",
                status="ACTIVE",
                created_at=now,
                subscription_configuration_status="MISSING",
                missing_fields=["plan", "start_date"],
            )
        ],
    )

    app.dependency_overrides[get_shopflow_client] = lambda: mock_client
    try:
        res = await client.get(
            "/api/v1/shopflow/shops/without-subscription",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res.status_code == 200
        data = res.json()
        assert data["meta"]["total"] == 1
        assert len(data["shops"]) == 1
        assert data["shops"][0]["subscription_configuration_status"] == "MISSING"
    finally:
        app.dependency_overrides.pop(get_shopflow_client, None)


@pytest.mark.asyncio
async def test_all_subscriptions_listing(client: AsyncClient, read_only_employee: CloudUser):
    token = await get_token_for(client, "employee@cryvex.com", "EmployeePass123!")
    tenant_id = uuid.uuid4()
    sub_id = uuid.uuid4()
    now = datetime.now(timezone.utc)

    mock_client = AsyncMock(spec=ShopFlowClient)
    mock_client.list_subscriptions.return_value = CloudShopSubscriptionListResponse(
        meta=PaginatedMeta(total=1, limit=50, offset=0),
        subscriptions=[
            CloudShopSubscriptionItem(
                id=sub_id,
                tenant_id=tenant_id,
                shop_name="Alpha Store",
                business_name="Alpha Retail Ltd",
                shop_status="ACTIVE",
                plan="SHOPFLOW",
                status="ACTIVE",
                start_date=now,
                end_date=None,
                created_at=now,
                updated_at=now,
            )
        ],
    )

    app.dependency_overrides[get_shopflow_client] = lambda: mock_client
    try:
        res = await client.get(
            "/api/v1/shopflow/subscriptions",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res.status_code == 200
        data = res.json()
        assert data["meta"]["total"] == 1
        assert data["subscriptions"][0]["plan"] == "SHOPFLOW"
    finally:
        app.dependency_overrides.pop(get_shopflow_client, None)


@pytest.mark.asyncio
async def test_user_access_reset_endpoint(client: AsyncClient, superuser: CloudUser):
    token = await get_token_for(client, "admin@cryvex.com", "AdminPass123!")
    tenant_id = uuid.uuid4()
    user_id = uuid.uuid4()

    mock_client = AsyncMock(spec=ShopFlowClient)
    mock_client.reset_shop_user_access.return_value = CloudUserAccessResetResponse(
        success=True,
        user_id=user_id,
        tenant_id=tenant_id,
        status="pending_integration",
        message="Access reset workflow initiated",
        notification_delivery_supported=False,
        details="Temporary credentials dispatched or recorded in audit trail.",
    )

    app.dependency_overrides[get_shopflow_client] = lambda: mock_client
    try:
        res = await client.post(
            f"/api/v1/shopflow/shops/{tenant_id}/users/{user_id}/access-reset",
            headers={"Authorization": f"Bearer {token}"},
            json={"reason": "User forgot password and requested manual reset"},
        )
        assert res.status_code == 200
        data = res.json()
        assert data["success"] is True
        assert data["status"] == "pending_integration"
    finally:
        app.dependency_overrides.pop(get_shopflow_client, None)


@pytest.mark.asyncio
async def test_subscription_lifecycle_operations(client: AsyncClient, superuser: CloudUser):
    token = await get_token_for(client, "admin@cryvex.com", "AdminPass123!")
    tenant_id = uuid.uuid4()
    sub_id = uuid.uuid4()
    now = datetime.now(timezone.utc)

    mock_client = AsyncMock(spec=ShopFlowClient)
    mock_op_response = CloudSubscriptionOperationResponse(
        success=True,
        subscription_id=sub_id,
        tenant_id=tenant_id,
        plan="SHOPFLOW",
        status="ACTIVE",
        start_date=now,
        end_date=None,
        message="Subscription upgraded successfully",
    )
    mock_client.upgrade_shop_subscription.return_value = mock_op_response
    mock_client.downgrade_shop_subscription.return_value = mock_op_response
    mock_client.suspend_shop_subscription.return_value = mock_op_response
    mock_client.cancel_shop_subscription.return_value = mock_op_response

    app.dependency_overrides[get_shopflow_client] = lambda: mock_client
    try:
        # Upgrade
        res = await client.post(
            f"/api/v1/shopflow/shops/{tenant_id}/subscription/upgrade",
            headers={"Authorization": f"Bearer {token}"},
            json={"new_plan": "SHOPFLOW", "reason": "Upgrading to full plan"},
        )
        assert res.status_code == 200

        # Downgrade
        res = await client.post(
            f"/api/v1/shopflow/shops/{tenant_id}/subscription/downgrade",
            headers={"Authorization": f"Bearer {token}"},
            json={"new_plan": "TRIAL", "reason": "Downgrading to trial"},
        )
        assert res.status_code == 200

        # Suspend
        res = await client.post(
            f"/api/v1/shopflow/shops/{tenant_id}/subscription/suspend",
            headers={"Authorization": f"Bearer {token}"},
            json={"reason": "Payment failure"},
        )
        assert res.status_code == 200

        # Cancel
        res = await client.post(
            f"/api/v1/shopflow/shops/{tenant_id}/subscription/cancel",
            headers={"Authorization": f"Bearer {token}"},
            json={"reason": "Customer requested account cancellation"},
        )
        assert res.status_code == 200
    finally:
        app.dependency_overrides.pop(get_shopflow_client, None)
