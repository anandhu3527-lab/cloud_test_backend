"""
Unit tests for ShopFlow HTTP client.
"""

from datetime import datetime, timezone
from decimal import Decimal
import uuid
import httpx
import pytest

from app.integrations.shopflow.auth import SHOPFLOW_SERVICE_TOKEN_HEADER, get_service_headers
from app.integrations.shopflow.client import ShopFlowClient
from app.integrations.shopflow.exceptions import (
    ShopFlowAuthError,
    ShopFlowConflictError,
    ShopFlowConnectionError,
    ShopFlowNotConfiguredError,
    ShopFlowNotFoundError,
    ShopFlowRateLimitError,
    ShopFlowServerError,
    ShopFlowTimeoutError,
    ShopFlowValidationError,
)
from app.integrations.shopflow.schemas import (
    CloudShopDetailResponse,
    CloudSubscriptionActivationRequest,
    CloudSubscriptionChangeRequest,
    OverallDashboardMetrics,
)


@pytest.mark.asyncio
async def test_auth_headers_construction():
    headers = get_service_headers("test-secret-token")
    assert headers[SHOPFLOW_SERVICE_TOKEN_HEADER] == "test-secret-token"
    assert headers["Accept"] == "application/json"


@pytest.mark.asyncio
async def test_auth_missing_token_fails_closed():
    with pytest.raises(ShopFlowNotConfiguredError):
        get_service_headers("")
    with pytest.raises(ShopFlowNotConfiguredError):
        get_service_headers("   ")


@pytest.mark.asyncio
async def test_client_missing_token_rejects_request():
    client = ShopFlowClient(base_url="http://mock-shopflow", service_token="")
    with pytest.raises(ShopFlowNotConfiguredError):
        await client.get_overview()


@pytest.mark.asyncio
async def test_client_sends_correct_header_and_url():
    captured_request: httpx.Request | None = None

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal captured_request
        captured_request = request
        return httpx.Response(
            200,
            json={
                "total_shops": 10,
                "active_shops": 8,
                "trial_shops": 2,
                "suspended_shops": 0,
                "expired_shops": 0,
                "new_shops_this_month": 3,
                "active_users": 25,
                "bills_generated_today": 12,
                "monthly_revenue": "45000.50",
            },
        )

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as mock_httpx:
        client = ShopFlowClient(
            base_url="http://mock-shopflow",
            service_token="valid-token",
            client=mock_httpx,
        )
        res = await client.get_overview()

        assert isinstance(res, OverallDashboardMetrics)
        assert res.total_shops == 10
        assert res.monthly_revenue == Decimal("45000.50")
        assert captured_request is not None
        assert captured_request.url == "http://mock-shopflow/api/v1/internal/cloud/overview"
        assert captured_request.headers[SHOPFLOW_SERVICE_TOKEN_HEADER] == "valid-token"


@pytest.mark.asyncio
async def test_client_timeout_handling():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException("Connection timed out")

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as mock_httpx:
        client = ShopFlowClient(
            base_url="http://mock-shopflow",
            service_token="valid-token",
            client=mock_httpx,
        )
        with pytest.raises(ShopFlowTimeoutError) as exc_info:
            await client.get_overview()
        assert "timed out" in str(exc_info.value.message).lower()


@pytest.mark.asyncio
async def test_client_connection_error_handling():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("Connection refused")

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as mock_httpx:
        client = ShopFlowClient(
            base_url="http://mock-shopflow",
            service_token="valid-token",
            client=mock_httpx,
        )
        with pytest.raises(ShopFlowConnectionError) as exc_info:
            await client.get_overview()
        assert "unable to connect" in str(exc_info.value.message).lower()


@pytest.mark.asyncio
async def test_client_upstream_401_403_handling():
    for status_code in (401, 403):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(status_code, json={"detail": "Unauthorized internal service"})

        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as mock_httpx:
            client = ShopFlowClient(
                base_url="http://mock-shopflow",
                service_token="invalid-token",
                client=mock_httpx,
            )
            with pytest.raises(ShopFlowAuthError) as exc_info:
                await client.get_overview()
            assert exc_info.value.status_code == 502
            # Verify the token is never leaked in the exception message
            assert "invalid-token" not in str(exc_info.value.message)


@pytest.mark.asyncio
async def test_client_upstream_404_handling():
    tenant_id = uuid.uuid4()

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"detail": f"Shop {tenant_id} not found"})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as mock_httpx:
        client = ShopFlowClient(
            base_url="http://mock-shopflow",
            service_token="valid-token",
            client=mock_httpx,
        )
        with pytest.raises(ShopFlowNotFoundError) as exc_info:
            await client.get_shop(tenant_id)
        assert exc_info.value.status_code == 404
        assert str(tenant_id) in exc_info.value.message


@pytest.mark.asyncio
async def test_client_upstream_409_conflict_handling():
    tenant_id = uuid.uuid4()

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(409, json={"detail": "Shop already has an active subscription"})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as mock_httpx:
        client = ShopFlowClient(
            base_url="http://mock-shopflow",
            service_token="valid-token",
            client=mock_httpx,
        )
        payload = CloudSubscriptionActivationRequest(
            plan="SHOPFLOW",
            status="ACTIVE",
            start_date=datetime(2026, 1, 1, tzinfo=timezone.utc),
            end_date=datetime(2027, 1, 1, tzinfo=timezone.utc),
            reason="Activating new subscription",
        )
        with pytest.raises(ShopFlowConflictError) as exc_info:
            await client.activate_shop_subscription(tenant_id, payload)
        assert exc_info.value.status_code == 409
        assert "already has an active subscription" in exc_info.value.message


@pytest.mark.asyncio
async def test_client_upstream_422_validation_handling():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(422, json={"detail": [{"loc": ["body", "plan"], "msg": "Invalid plan"}]})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as mock_httpx:
        client = ShopFlowClient(
            base_url="http://mock-shopflow",
            service_token="valid-token",
            client=mock_httpx,
        )
        with pytest.raises(ShopFlowValidationError) as exc_info:
            await client.get_overview()
        assert exc_info.value.status_code == 422


@pytest.mark.asyncio
async def test_client_upstream_429_ratelimit_handling():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, json={"detail": "Rate limit exceeded"})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as mock_httpx:
        client = ShopFlowClient(
            base_url="http://mock-shopflow",
            service_token="valid-token",
            client=mock_httpx,
        )
        with pytest.raises(ShopFlowRateLimitError) as exc_info:
            await client.get_overview()
        assert exc_info.value.status_code == 429


@pytest.mark.asyncio
async def test_client_upstream_500_handling():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="Internal Server Error")

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as mock_httpx:
        client = ShopFlowClient(
            base_url="http://mock-shopflow",
            service_token="valid-token",
            client=mock_httpx,
        )
        with pytest.raises(ShopFlowServerError) as exc_info:
            await client.get_overview()
        assert exc_info.value.status_code == 502


@pytest.mark.asyncio
async def test_client_invalid_response_structure_handling():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"unexpected_field": 123})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as mock_httpx:
        client = ShopFlowClient(
            base_url="http://mock-shopflow",
            service_token="valid-token",
            client=mock_httpx,
        )
        with pytest.raises(ShopFlowServerError) as exc_info:
            await client.get_overview()
        assert "unexpected response structure" in exc_info.value.message
