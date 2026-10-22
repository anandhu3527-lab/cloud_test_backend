"""
Dedicated Regression Tests for ShopFlow Subscription Revenue on CRYVEX Cloud Dashboard.

Covers all 9 required business and regression scenarios:
1. Zero eligible paid shops.
2. One eligible paid shop = ₹399/month.
3. Ten eligible paid shops = ₹3,990/month.
4. Shops without subscription records are excluded.
5. Trial and suspended subscriptions are excluded.
6. Expired subscriptions are excluded.
7. Start/end dates are respected (future start dates & past end dates excluded).
8. Existing dashboard metrics remain unchanged.
9. ShopFlow integration failures are handled safely and are not misreported as zero revenue.
"""

import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import AsyncMock

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import permissions as perm_constants
from app.core.security import get_password_hash
from app.integrations.shopflow.client import ShopFlowClient, get_shopflow_client
from app.integrations.shopflow.exceptions import (
    ShopFlowConnectionError,
    ShopFlowServerError,
)
from app.integrations.shopflow.schemas import (
    CloudShopSubscriptionItem,
    CloudShopSubscriptionListResponse,
    OverallDashboardMetrics,
    PaginatedMeta,
)
from app.main import app
from app.models.cloud_permission import CloudPermission
from app.models.cloud_role import CloudRole
from app.models.cloud_user import CloudUser
from app.models.role_permission import CloudRolePermission
from app.services.shopflow.overview_service import (
    MONTHLY_SHOPFLOW_SUBSCRIPTION_PRICE,
    calculate_shopflow_revenue,
    is_subscription_eligible_for_paid_revenue,
)


# ============================================================
# FIXTURES
# ============================================================

@pytest.fixture
async def dashboard_user(db_session: AsyncSession) -> CloudUser:
    """Create a user with dashboard view & shopflow read permissions."""
    role = CloudRole(name="EMPLOYEE_REV", description="Standard employee access")
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
        email="analyst@cryvex.com",
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


async def get_auth_headers(client: AsyncClient, email: str = "analyst@cryvex.com") -> dict[str, str]:
    """Helper to login and obtain Bearer token."""
    login_res = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "EmployeePass123!"},
    )
    assert login_res.status_code == 200, f"Login failed: {login_res.text}"
    token = login_res.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def create_subscription_item(
    tenant_id: uuid.UUID | None = None,
    plan: str = "SHOPFLOW",
    status: str = "ACTIVE",
    start_date: datetime | None = None,
    end_date: datetime | None = None,
) -> CloudShopSubscriptionItem:
    """Helper to generate subscription items for test cases."""
    now = datetime.now(timezone.utc)
    t_id = tenant_id or uuid.uuid4()
    return CloudShopSubscriptionItem(
        id=uuid.uuid4(),
        tenant_id=t_id,
        shop_name=f"Shop {t_id.hex[:4]}",
        business_name=f"Business {t_id.hex[:4]} Ltd",
        shop_status="ACTIVE",
        plan=plan,
        status=status,
        start_date=start_date or (now - timedelta(days=30)),
        end_date=end_date,
        created_at=now - timedelta(days=30),
        updated_at=now,
    )


# ============================================================
# UNIT TESTS: ELIGIBILITY & CALCULATION RULES
# ============================================================

def test_unit_subscription_eligibility_rules():
    """Verify subscription eligibility business rules in isolation."""
    now = datetime.now(timezone.utc)

    # 1. Active ShopFlow plan within valid dates -> Eligible
    valid_sub = create_subscription_item(plan="SHOPFLOW", status="ACTIVE")
    assert is_subscription_eligible_for_paid_revenue(valid_sub, now) is True

    # 2. Trial plan -> Excluded
    trial_sub = create_subscription_item(plan="TRIAL", status="ACTIVE")
    assert is_subscription_eligible_for_paid_revenue(trial_sub, now) is False

    # 3. Suspended / Cancelled / Expired status -> Excluded
    assert is_subscription_eligible_for_paid_revenue(create_subscription_item(status="SUSPENDED"), now) is False
    assert is_subscription_eligible_for_paid_revenue(create_subscription_item(status="CANCELLED"), now) is False
    assert is_subscription_eligible_for_paid_revenue(create_subscription_item(status="EXPIRED"), now) is False

    # 4. Empty / None plan -> Excluded
    assert is_subscription_eligible_for_paid_revenue(create_subscription_item(plan=""), now) is False

    # 5. Future start date -> Excluded
    future_sub = create_subscription_item(start_date=now + timedelta(days=10))
    assert is_subscription_eligible_for_paid_revenue(future_sub, now) is False

    # 6. Past end date (expired) -> Excluded
    expired_date_sub = create_subscription_item(end_date=now - timedelta(days=1))
    assert is_subscription_eligible_for_paid_revenue(expired_date_sub, now) is False

    # 7. Future end date -> Eligible
    future_end_sub = create_subscription_item(end_date=now + timedelta(days=60))
    assert is_subscription_eligible_for_paid_revenue(future_end_sub, now) is True

    # 8. None sub -> Excluded
    assert is_subscription_eligible_for_paid_revenue(None, now) is False


def test_unit_revenue_calculation_scaling_and_deduplication():
    """Verify revenue calculation formula: Count * 399."""
    now = datetime.now(timezone.utc)

    # 0 shops
    count, rev, price = calculate_shopflow_revenue([], now)
    assert count == 0
    assert rev == Decimal("0.00")
    assert price == Decimal("399.00")

    # 1 shop = 399
    sub1 = create_subscription_item()
    count, rev, _ = calculate_shopflow_revenue([sub1], now)
    assert count == 1
    assert rev == Decimal("399.00")

    # 10 shops = 3,990
    subs_10 = [create_subscription_item() for _ in range(10)]
    count, rev, _ = calculate_shopflow_revenue(subs_10, now)
    assert count == 10
    assert rev == Decimal("3990.00")

    # Deduplication test: duplicate subscription for same tenant
    same_tenant = uuid.uuid4()
    sub_dup1 = create_subscription_item(tenant_id=same_tenant)
    sub_dup2 = create_subscription_item(tenant_id=same_tenant)
    count, rev, _ = calculate_shopflow_revenue([sub_dup1, sub_dup2], now)
    assert count == 1
    assert rev == Decimal("399.00")


# ============================================================
# API TESTS: DASHBOARD ENDPOINT SCENARIOS
# ============================================================

@pytest.mark.asyncio
async def test_case_1_zero_eligible_paid_shops(client: AsyncClient, dashboard_user: CloudUser):
    """Scenario 1: Zero eligible paid shops returns 0 count and ₹0/month."""
    headers = await get_auth_headers(client, dashboard_user.email)

    mock_client = AsyncMock(spec=ShopFlowClient)
    mock_client.get_overview.return_value = OverallDashboardMetrics(
        total_shops=5,
        active_shops=5,
        trial_shops=5,
        suspended_shops=0,
        expired_shops=0,
        new_shops_this_month=1,
        active_users=10,
        bills_generated_today=2,
        monthly_revenue=Decimal("12000.00"),
    )
    # Only trial subscriptions
    trial_subs = [create_subscription_item(plan="TRIAL") for _ in range(3)]
    mock_client.list_subscriptions.return_value = CloudShopSubscriptionListResponse(
        meta=PaginatedMeta(total=3, limit=100, offset=0),
        subscriptions=trial_subs,
    )

    app.dependency_overrides[get_shopflow_client] = lambda: mock_client
    try:
        res = await client.get("/api/v1/shopflow/overview", headers=headers)
        assert res.status_code == 200
        data = res.json()
        assert data["active_paid_shopflow_shops"] == 0
        assert Decimal(str(data["shopflow_monthly_revenue"])) == Decimal("0.00")
        assert Decimal(str(data["shopflow_revenue"])) == Decimal("0.00")
        assert Decimal(str(data["shopflow_monthly_price"])) == Decimal("399.00")
    finally:
        app.dependency_overrides.pop(get_shopflow_client, None)


@pytest.mark.asyncio
async def test_case_2_one_eligible_paid_shop(client: AsyncClient, dashboard_user: CloudUser):
    """Scenario 2: One eligible paid shop returns 1 count and ₹399/month."""
    headers = await get_auth_headers(client, dashboard_user.email)

    mock_client = AsyncMock(spec=ShopFlowClient)
    mock_client.get_overview.return_value = OverallDashboardMetrics(
        total_shops=1,
        active_shops=1,
        trial_shops=0,
        suspended_shops=0,
        expired_shops=0,
        new_shops_this_month=1,
        active_users=2,
        bills_generated_today=5,
        monthly_revenue=Decimal("4500.00"),
    )
    single_sub = [create_subscription_item(plan="SHOPFLOW", status="ACTIVE")]
    mock_client.list_subscriptions.return_value = CloudShopSubscriptionListResponse(
        meta=PaginatedMeta(total=1, limit=100, offset=0),
        subscriptions=single_sub,
    )

    app.dependency_overrides[get_shopflow_client] = lambda: mock_client
    try:
        res = await client.get("/api/v1/shopflow/overview", headers=headers)
        assert res.status_code == 200
        data = res.json()
        assert data["active_paid_shopflow_shops"] == 1
        assert Decimal(str(data["shopflow_monthly_revenue"])) == Decimal("399.00")
        assert Decimal(str(data["shopflow_revenue"])) == Decimal("399.00")
        assert Decimal(str(data["shopflow_monthly_price"])) == Decimal("399.00")
    finally:
        app.dependency_overrides.pop(get_shopflow_client, None)


@pytest.mark.asyncio
async def test_case_3_ten_eligible_paid_shops(client: AsyncClient, dashboard_user: CloudUser):
    """Scenario 3: Ten eligible paid shops returns 10 count and ₹3,990/month."""
    headers = await get_auth_headers(client, dashboard_user.email)

    mock_client = AsyncMock(spec=ShopFlowClient)
    mock_client.get_overview.return_value = OverallDashboardMetrics(
        total_shops=15,
        active_shops=12,
        trial_shops=2,
        suspended_shops=1,
        expired_shops=0,
        new_shops_this_month=4,
        active_users=40,
        bills_generated_today=25,
        monthly_revenue=Decimal("85000.00"),
    )
    ten_subs = [create_subscription_item(plan="SHOPFLOW", status="ACTIVE") for _ in range(10)]
    mock_client.list_subscriptions.return_value = CloudShopSubscriptionListResponse(
        meta=PaginatedMeta(total=10, limit=100, offset=0),
        subscriptions=ten_subs,
    )

    app.dependency_overrides[get_shopflow_client] = lambda: mock_client
    try:
        res = await client.get("/api/v1/shopflow/overview", headers=headers)
        assert res.status_code == 200
        data = res.json()
        assert data["active_paid_shopflow_shops"] == 10
        assert Decimal(str(data["shopflow_monthly_revenue"])) == Decimal("3990.00")
        assert Decimal(str(data["shopflow_revenue"])) == Decimal("3990.00")
    finally:
        app.dependency_overrides.pop(get_shopflow_client, None)


@pytest.mark.asyncio
async def test_case_4_shops_without_subscriptions_excluded(client: AsyncClient, dashboard_user: CloudUser):
    """Scenario 4: Total shops = 20, but only 3 have active paid subscriptions -> ₹1,197/month."""
    headers = await get_auth_headers(client, dashboard_user.email)

    mock_client = AsyncMock(spec=ShopFlowClient)
    mock_client.get_overview.return_value = OverallDashboardMetrics(
        total_shops=20,
        active_shops=18,
        trial_shops=0,
        suspended_shops=2,
        expired_shops=0,
        new_shops_this_month=5,
        active_users=50,
        bills_generated_today=30,
        monthly_revenue=Decimal("90000.00"),
    )
    # Only 3 shops have actual active SHOPFLOW subscription records
    three_subs = [create_subscription_item(plan="SHOPFLOW", status="ACTIVE") for _ in range(3)]
    mock_client.list_subscriptions.return_value = CloudShopSubscriptionListResponse(
        meta=PaginatedMeta(total=3, limit=100, offset=0),
        subscriptions=three_subs,
    )

    app.dependency_overrides[get_shopflow_client] = lambda: mock_client
    try:
        res = await client.get("/api/v1/shopflow/overview", headers=headers)
        assert res.status_code == 200
        data = res.json()
        # Even though total_shops=20 and active_shops=18, only 3 paid subscriptions exist
        assert data["total_shops"] == 20
        assert data["active_paid_shopflow_shops"] == 3
        assert Decimal(str(data["shopflow_monthly_revenue"])) == Decimal("1197.00")
    finally:
        app.dependency_overrides.pop(get_shopflow_client, None)


@pytest.mark.asyncio
async def test_case_5_trial_and_suspended_excluded(client: AsyncClient, dashboard_user: CloudUser):
    """Scenario 5: Mixed subscriptions with trial, suspended, and cancelled excluded."""
    headers = await get_auth_headers(client, dashboard_user.email)

    now = datetime.now(timezone.utc)
    mock_client = AsyncMock(spec=ShopFlowClient)
    mock_client.get_overview.return_value = OverallDashboardMetrics(
        total_shops=10,
        active_shops=8,
        trial_shops=4,
        suspended_shops=2,
        expired_shops=0,
        new_shops_this_month=2,
        active_users=20,
        bills_generated_today=10,
        monthly_revenue=Decimal("30000.00"),
    )

    mixed_subs = [
        create_subscription_item(plan="SHOPFLOW", status="ACTIVE"),  # Eligible 1
        create_subscription_item(plan="SHOPFLOW", status="ACTIVE"),  # Eligible 2
        create_subscription_item(plan="TRIAL", status="ACTIVE"),     # Excluded (Trial)
        create_subscription_item(plan="TRIAL", status="ACTIVE"),     # Excluded (Trial)
        create_subscription_item(plan="SHOPFLOW", status="SUSPENDED"), # Excluded (Suspended)
        create_subscription_item(plan="SHOPFLOW", status="CANCELLED"), # Excluded (Cancelled)
    ]
    mock_client.list_subscriptions.return_value = CloudShopSubscriptionListResponse(
        meta=PaginatedMeta(total=len(mixed_subs), limit=100, offset=0),
        subscriptions=mixed_subs,
    )

    app.dependency_overrides[get_shopflow_client] = lambda: mock_client
    try:
        res = await client.get("/api/v1/shopflow/overview", headers=headers)
        assert res.status_code == 200
        data = res.json()
        # Only the 2 active SHOPFLOW subscriptions are counted
        assert data["active_paid_shopflow_shops"] == 2
        assert Decimal(str(data["shopflow_monthly_revenue"])) == Decimal("798.00")
    finally:
        app.dependency_overrides.pop(get_shopflow_client, None)


@pytest.mark.asyncio
async def test_case_6_expired_subscriptions_excluded(client: AsyncClient, dashboard_user: CloudUser):
    """Scenario 6: Expired status or end_date in past are excluded."""
    headers = await get_auth_headers(client, dashboard_user.email)

    now = datetime.now(timezone.utc)
    mock_client = AsyncMock(spec=ShopFlowClient)
    mock_client.get_overview.return_value = OverallDashboardMetrics(
        total_shops=5,
        active_shops=3,
        trial_shops=0,
        suspended_shops=0,
        expired_shops=2,
        new_shops_this_month=0,
        active_users=10,
        bills_generated_today=5,
        monthly_revenue=Decimal("15000.00"),
    )

    subs = [
        create_subscription_item(plan="SHOPFLOW", status="ACTIVE"),  # Eligible 1
        create_subscription_item(plan="SHOPFLOW", status="EXPIRED"), # Excluded (EXPIRED status)
        create_subscription_item(                                    # Excluded (past end_date)
            plan="SHOPFLOW",
            status="ACTIVE",
            end_date=now - timedelta(days=2),
        ),
    ]
    mock_client.list_subscriptions.return_value = CloudShopSubscriptionListResponse(
        meta=PaginatedMeta(total=len(subs), limit=100, offset=0),
        subscriptions=subs,
    )

    app.dependency_overrides[get_shopflow_client] = lambda: mock_client
    try:
        res = await client.get("/api/v1/shopflow/overview", headers=headers)
        assert res.status_code == 200
        data = res.json()
        assert data["active_paid_shopflow_shops"] == 1
        assert Decimal(str(data["shopflow_monthly_revenue"])) == Decimal("399.00")
    finally:
        app.dependency_overrides.pop(get_shopflow_client, None)


@pytest.mark.asyncio
async def test_case_7_start_and_end_dates_respected(client: AsyncClient, dashboard_user: CloudUser):
    """Scenario 7: Future start dates are excluded; valid ongoing and unexpired dates are included."""
    headers = await get_auth_headers(client, dashboard_user.email)

    now = datetime.now(timezone.utc)
    mock_client = AsyncMock(spec=ShopFlowClient)
    mock_client.get_overview.return_value = OverallDashboardMetrics(
        total_shops=6,
        active_shops=6,
        trial_shops=0,
        suspended_shops=0,
        expired_shops=0,
        new_shops_this_month=2,
        active_users=15,
        bills_generated_today=8,
        monthly_revenue=Decimal("25000.00"),
    )

    subs = [
        # 1. Valid: started 10 days ago, no end_date -> Eligible
        create_subscription_item(start_date=now - timedelta(days=10), end_date=None),
        # 2. Valid: started 30 days ago, ends in 15 days -> Eligible
        create_subscription_item(start_date=now - timedelta(days=30), end_date=now + timedelta(days=15)),
        # 3. Future start: starts in 5 days -> Excluded
        create_subscription_item(start_date=now + timedelta(days=5), end_date=now + timedelta(days=365)),
        # 4. Past end: ended 2 days ago -> Excluded
        create_subscription_item(start_date=now - timedelta(days=60), end_date=now - timedelta(days=2)),
    ]
    mock_client.list_subscriptions.return_value = CloudShopSubscriptionListResponse(
        meta=PaginatedMeta(total=len(subs), limit=100, offset=0),
        subscriptions=subs,
    )

    app.dependency_overrides[get_shopflow_client] = lambda: mock_client
    try:
        res = await client.get("/api/v1/shopflow/overview", headers=headers)
        assert res.status_code == 200
        data = res.json()
        assert data["active_paid_shopflow_shops"] == 2
        assert Decimal(str(data["shopflow_monthly_revenue"])) == Decimal("798.00")
    finally:
        app.dependency_overrides.pop(get_shopflow_client, None)


@pytest.mark.asyncio
async def test_case_8_existing_dashboard_metrics_preserved(client: AsyncClient, dashboard_user: CloudUser):
    """Scenario 8: Existing dashboard metrics remain completely unchanged."""
    headers = await get_auth_headers(client, dashboard_user.email)

    mock_client = AsyncMock(spec=ShopFlowClient)
    mock_client.get_overview.return_value = OverallDashboardMetrics(
        total_shops=42,
        active_shops=35,
        trial_shops=7,
        suspended_shops=3,
        expired_shops=4,
        new_shops_this_month=11,
        active_users=128,
        bills_generated_today=64,
        monthly_revenue=Decimal("123456.78"),
    )
    five_subs = [create_subscription_item() for _ in range(5)]
    mock_client.list_subscriptions.return_value = CloudShopSubscriptionListResponse(
        meta=PaginatedMeta(total=5, limit=100, offset=0),
        subscriptions=five_subs,
    )

    app.dependency_overrides[get_shopflow_client] = lambda: mock_client
    try:
        res = await client.get("/api/v1/shopflow/overview", headers=headers)
        assert res.status_code == 200
        data = res.json()

        # Check existing metrics are strictly preserved
        assert data["total_shops"] == 42
        assert data["active_shops"] == 35
        assert data["trial_shops"] == 7
        assert data["suspended_shops"] == 3
        assert data["expired_shops"] == 4
        assert data["new_shops_this_month"] == 11
        assert data["active_users"] == 128
        assert data["bills_generated_today"] == 64
        assert Decimal(str(data["monthly_revenue"])) == Decimal("123456.78")

        # Check new revenue metrics
        assert data["active_paid_shopflow_shops"] == 5
        assert Decimal(str(data["shopflow_monthly_revenue"])) == Decimal("1995.00")
        assert Decimal(str(data["shopflow_revenue"])) == Decimal("1995.00")
    finally:
        app.dependency_overrides.pop(get_shopflow_client, None)


@pytest.mark.asyncio
async def test_case_9_shopflow_integration_failures_not_misreported_as_zero(client: AsyncClient, dashboard_user: CloudUser):
    """
    Scenario 9: Upstream ShopFlow failures are handled safely and
    propagate appropriate HTTP error responses (e.g. 502 Bad Gateway),
    and are NOT silently caught and misreported as ₹0 revenue.
    """
    headers = await get_auth_headers(client, dashboard_user.email)

    # 1. Connection error on get_overview
    mock_client_conn = AsyncMock(spec=ShopFlowClient)
    mock_client_conn.get_overview.side_effect = ShopFlowConnectionError("Cannot connect to ShopFlow")

    app.dependency_overrides[get_shopflow_client] = lambda: mock_client_conn
    try:
        res1 = await client.get("/api/v1/shopflow/overview", headers=headers)
        assert res1.status_code == 502
    finally:
        app.dependency_overrides.pop(get_shopflow_client, None)

    # 2. Server error on list_subscriptions
    mock_client_sub = AsyncMock(spec=ShopFlowClient)
    mock_client_sub.get_overview.return_value = OverallDashboardMetrics(
        total_shops=10,
        active_shops=8,
        trial_shops=2,
        suspended_shops=0,
        expired_shops=0,
        new_shops_this_month=1,
        active_users=20,
        bills_generated_today=5,
        monthly_revenue=Decimal("15000.00"),
    )
    mock_client_sub.list_subscriptions.side_effect = ShopFlowServerError("ShopFlow database internal error")

    app.dependency_overrides[get_shopflow_client] = lambda: mock_client_sub
    try:
        res2 = await client.get("/api/v1/shopflow/overview", headers=headers)
        assert res2.status_code == 502
    finally:
        app.dependency_overrides.pop(get_shopflow_client, None)
