"""
Asynchronous HTTP client for communicating with the ShopFlow backend.
"""

from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator, Type, TypeVar
from uuid import UUID
import httpx
from pydantic import BaseModel

from app.core.config import settings
from app.core.logging import get_logger
from app.integrations.shopflow import endpoints
from app.integrations.shopflow.auth import get_service_headers
from app.integrations.shopflow.exceptions import (
    ShopFlowAuthError,
    ShopFlowConflictError,
    ShopFlowConnectionError,
    ShopFlowError,
    ShopFlowNotConfiguredError,
    ShopFlowNotFoundError,
    ShopFlowRateLimitError,
    ShopFlowServerError,
    ShopFlowTimeoutError,
    ShopFlowValidationError,
)
from app.integrations.shopflow.schemas import (
    BillsOverviewMetrics,
    CloudAuditLogListResponse,
    CloudBillListResponse,
    CloudCustomerListResponse,
    CloudProductDetailResponse,
    CloudProductListResponse,
    CloudProductUsageResponse,
    CloudProductVariantItem,
    CloudShopActivityResponse,
    CloudShopBillingSummary,
    CloudShopDetailResponse,
    CloudShopKPIs,
    CloudShopListResponse,
    CloudShopStatusUpdateRequest,
    CloudShopStatusUpdateResponse,
    CloudShopSubscriptionListResponse,
    CloudShopUsageResponse,
    CloudStockSummaryResponse,
    CloudSubscriptionActionRequest,
    CloudSubscriptionActivationRequest,
    CloudSubscriptionActivationResponse,
    CloudSubscriptionChangeRequest,
    CloudSubscriptionDetail,
    CloudSubscriptionHistoryResponse,
    CloudSubscriptionOperationResponse,
    CloudSupportResponse,
    CloudUserAccessResetRequest,
    CloudUserAccessResetResponse,
    CloudUserDetailResponse,
    CloudUserListResponse,
    CloudUserStatusUpdateRequest,
    CloudUserStatusUpdateResponse,
    OverallDashboardMetrics,
    ShopsWithoutSubscriptionResponse,
    SubscriptionOverviewMetrics,
    SystemHealthResponse,
)

logger = get_logger("shopflow_client")
T = TypeVar("T", bound=BaseModel)


class ShopFlowClient:
    """
    HTTP client for ShopFlow Internal Cloud API.
    
    Security rules:
    - Never log tokens or sensitive payload values.
    - Fails closed if service token is missing or unconfigured.
    - Avoid unsafe automatic retries on state-changing operations.
    """

    def __init__(
        self,
        base_url: str | None = None,
        service_token: str | None = None,
        timeout: float | None = None,
        client: httpx.AsyncClient | None = None,
    ):
        self.base_url = (base_url or settings.SHOPFLOW_BASE_URL).rstrip("/")
        self.service_token = (
            service_token if service_token is not None else settings.SHOPFLOW_SERVICE_TOKEN
        )
        self.timeout = timeout if timeout is not None else settings.SHOPFLOW_TIMEOUT_SECONDS
        self._external_client = client
        self._owned_client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._external_client is not None:
            return self._external_client
        if self._owned_client is None or self._owned_client.is_closed:
            self._owned_client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=httpx.Timeout(self.timeout),
            )
        return self._owned_client

    async def close(self) -> None:
        if self._owned_client is not None and not self._owned_client.is_closed:
            await self._owned_client.aclose()
            self._owned_client = None

    def _extract_error_detail(self, response: httpx.Response, default: str) -> str:
        try:
            body = response.json()
            if isinstance(body, dict):
                detail = body.get("detail") or body.get("message")
                if isinstance(detail, str):
                    return detail
                if isinstance(detail, list) and detail:
                    return str(detail[0].get("msg", detail[0]))
        except Exception:
            pass
        return default

    async def request(
        self,
        method: str,
        path: str,
        params: dict[str, Any] | None = None,
        json: Any | None = None,
        response_model: Type[T] | None = None,
    ) -> Any:
        headers = get_service_headers(self.service_token)
        client = await self._get_client()

        # Filter out None values from query parameters
        clean_params = None
        if params is not None:
            clean_params = {
                k: (v.isoformat() if hasattr(v, "isoformat") else str(v) if isinstance(v, (UUID, bool)) else v)
                for k, v in params.items()
                if v is not None
            }

        url = f"{self.base_url}{path}" if path.startswith("/") else f"{self.base_url}/{path}"

        try:
            response = await client.request(
                method=method,
                url=url,
                params=clean_params,
                json=json,
                headers=headers,
            )
        except httpx.TimeoutException as exc:
            logger.warning(f"ShopFlow request timed out: {method} {path}")
            raise ShopFlowTimeoutError(
                f"ShopFlow request timed out after {self.timeout}s"
            ) from exc
        except (httpx.ConnectError, httpx.NetworkError) as exc:
            logger.warning(f"Failed to connect to ShopFlow at {self.base_url}: {exc}")
            raise ShopFlowConnectionError(
                "Unable to connect to ShopFlow service. Please ensure the service is running."
            ) from exc
        except httpx.HTTPError as exc:
            logger.error(f"ShopFlow HTTP transport error: {exc}")
            raise ShopFlowServerError("ShopFlow HTTP transport error") from exc

        # Handle status codes
        if 200 <= response.status_code < 300:
            if response.status_code == 204 or not response.content:
                return None
            try:
                data = response.json()
            except Exception as e:
                logger.error(f"Invalid JSON response from ShopFlow: {e}")
                raise ShopFlowServerError("Invalid JSON received from ShopFlow service") from e

            if response_model is not None:
                try:
                    if isinstance(data, list):
                        return [response_model.model_validate(item) for item in data]
                    return response_model.model_validate(data)
                except Exception as ve:
                    logger.error(f"Failed to validate ShopFlow response against {response_model.__name__}: {ve}")
                    raise ShopFlowServerError("ShopFlow returned an unexpected response structure") from ve
            return data

        detail = self._extract_error_detail(response, response.text or "Upstream error")

        if response.status_code in (401, 403):
            logger.warning(f"ShopFlow service authentication failed (HTTP {response.status_code})")
            raise ShopFlowAuthError(
                "ShopFlow service rejected authentication credential",
                status_code=502,
            )
        elif response.status_code == 404:
            raise ShopFlowNotFoundError(detail)
        elif response.status_code == 409:
            raise ShopFlowConflictError(detail)
        elif response.status_code == 422:
            raise ShopFlowValidationError(detail)
        elif response.status_code == 429:
            raise ShopFlowRateLimitError("ShopFlow rate limit exceeded")
        elif response.status_code >= 500:
            logger.error(f"ShopFlow service returned 5xx (HTTP {response.status_code}): {detail}")
            raise ShopFlowServerError(f"ShopFlow service error: {detail}")
        else:
            raise ShopFlowError(
                message=f"ShopFlow returned unexpected status code {response.status_code}: {detail}",
                status_code=response.status_code,
            )

    # ============================================================
    # OVERVIEW & SYSTEM HEALTH
    # ============================================================

    async def get_overview(self) -> OverallDashboardMetrics:
        return await self.request("GET", endpoints.OVERVIEW, response_model=OverallDashboardMetrics)

    async def get_overview_health(self) -> SystemHealthResponse:
        return await self.request("GET", endpoints.OVERVIEW_HEALTH, response_model=SystemHealthResponse)

    async def get_overview_subscriptions(self) -> SubscriptionOverviewMetrics:
        return await self.request(
            "GET", endpoints.OVERVIEW_SUBSCRIPTIONS, response_model=SubscriptionOverviewMetrics
        )

    async def get_overview_bills(self) -> BillsOverviewMetrics:
        return await self.request("GET", endpoints.OVERVIEW_BILLS, response_model=BillsOverviewMetrics)

    # ============================================================
    # SHOPS
    # ============================================================

    async def list_shops(
        self,
        limit: int = 50,
        offset: int = 0,
        status: str | None = None,
        search: str | None = None,
    ) -> CloudShopListResponse:
        params = {"limit": limit, "offset": offset, "status": status, "search": search}
        return await self.request("GET", endpoints.SHOPS, params=params, response_model=CloudShopListResponse)

    async def list_shops_without_subscription(
        self,
        limit: int = 50,
        offset: int = 0,
    ) -> ShopsWithoutSubscriptionResponse:
        params = {"limit": limit, "offset": offset}
        return await self.request(
            "GET", endpoints.SHOPS_WITHOUT_SUBSCRIPTION, params=params, response_model=ShopsWithoutSubscriptionResponse
        )

    async def get_shop(self, tenant_id: UUID | str) -> CloudShopDetailResponse:
        return await self.request(
            "GET", endpoints.shop_detail_url(tenant_id), response_model=CloudShopDetailResponse
        )

    async def get_shop_overview(self, tenant_id: UUID | str) -> CloudShopKPIs:
        return await self.request(
            "GET", endpoints.shop_overview_url(tenant_id), response_model=CloudShopKPIs
        )

    async def get_shop_activity(
        self,
        tenant_id: UUID | str,
        limit: int = 50,
        offset: int = 0,
    ) -> CloudShopActivityResponse:
        params = {"limit": limit, "offset": offset}
        return await self.request(
            "GET", endpoints.shop_activity_url(tenant_id), params=params, response_model=CloudShopActivityResponse
        )

    async def update_shop_status(
        self,
        tenant_id: UUID | str,
        payload: CloudShopStatusUpdateRequest,
    ) -> CloudShopStatusUpdateResponse:
        return await self.request(
            "PATCH",
            endpoints.shop_status_url(tenant_id),
            json=payload.model_dump(),
            response_model=CloudShopStatusUpdateResponse,
        )

    # ============================================================
    # SHOP USERS
    # ============================================================

    async def list_shop_users(
        self,
        tenant_id: UUID | str,
        limit: int = 50,
        offset: int = 0,
        status: str | None = None,
    ) -> CloudUserListResponse:
        params = {"limit": limit, "offset": offset, "status": status}
        return await self.request(
            "GET", endpoints.shop_users_url(tenant_id), params=params, response_model=CloudUserListResponse
        )

    async def get_shop_user(
        self,
        tenant_id: UUID | str,
        user_id: UUID | str,
    ) -> CloudUserDetailResponse:
        return await self.request(
            "GET", endpoints.shop_user_detail_url(tenant_id, user_id), response_model=CloudUserDetailResponse
        )

    async def update_shop_user_status(
        self,
        tenant_id: UUID | str,
        user_id: UUID | str,
        payload: CloudUserStatusUpdateRequest,
    ) -> CloudUserStatusUpdateResponse:
        return await self.request(
            "PATCH",
            endpoints.shop_user_status_url(tenant_id, user_id),
            json=payload.model_dump(),
            response_model=CloudUserStatusUpdateResponse,
        )

    async def reset_shop_user_access(
        self,
        tenant_id: UUID | str,
        user_id: UUID | str,
        payload: CloudUserAccessResetRequest,
    ) -> CloudUserAccessResetResponse:
        return await self.request(
            "POST",
            endpoints.shop_user_access_reset_url(tenant_id, user_id),
            json=payload.model_dump(),
            response_model=CloudUserAccessResetResponse,
        )

    async def get_shop_user_activity(
        self,
        tenant_id: UUID | str,
        user_id: UUID | str,
        limit: int = 50,
        offset: int = 0,
    ) -> CloudShopActivityResponse:
        params = {"limit": limit, "offset": offset}
        return await self.request(
            "GET",
            endpoints.shop_user_activity_url(tenant_id, user_id),
            params=params,
            response_model=CloudShopActivityResponse,
        )

    # ============================================================
    # PRODUCTS & INVENTORY
    # ============================================================

    async def list_shop_products(
        self,
        tenant_id: UUID | str,
        limit: int = 50,
        offset: int = 0,
        status: str | None = None,
        search: str | None = None,
        low_stock_only: bool = False,
    ) -> CloudProductListResponse:
        params = {
            "limit": limit,
            "offset": offset,
            "status": status,
            "search": search,
            "low_stock_only": low_stock_only,
        }
        return await self.request(
            "GET", endpoints.shop_products_url(tenant_id), params=params, response_model=CloudProductListResponse
        )

    async def get_shop_stock_summary(self, tenant_id: UUID | str) -> CloudStockSummaryResponse:
        return await self.request(
            "GET", endpoints.shop_stock_summary_url(tenant_id), response_model=CloudStockSummaryResponse
        )

    async def get_shop_product_usage(self, tenant_id: UUID | str) -> CloudProductUsageResponse:
        return await self.request(
            "GET", endpoints.shop_product_usage_url(tenant_id), response_model=CloudProductUsageResponse
        )

    async def get_shop_product(
        self,
        tenant_id: UUID | str,
        product_id: UUID | str,
    ) -> CloudProductDetailResponse:
        return await self.request(
            "GET", endpoints.shop_product_detail_url(tenant_id, product_id), response_model=CloudProductDetailResponse
        )

    async def get_shop_product_variants(
        self,
        tenant_id: UUID | str,
        product_id: UUID | str,
    ) -> list[CloudProductVariantItem]:
        return await self.request(
            "GET",
            endpoints.shop_product_variants_url(tenant_id, product_id),
            response_model=CloudProductVariantItem,
        )

    # ============================================================
    # CUSTOMERS
    # ============================================================

    async def list_shop_customers(
        self,
        tenant_id: UUID | str,
        limit: int = 50,
        offset: int = 0,
        search: str | None = None,
        has_kadan_balance: bool | None = None,
    ) -> CloudCustomerListResponse:
        params = {
            "limit": limit,
            "offset": offset,
            "search": search,
            "has_kadan_balance": has_kadan_balance,
        }
        return await self.request(
            "GET", endpoints.shop_customers_url(tenant_id), params=params, response_model=CloudCustomerListResponse
        )

    # ============================================================
    # BILLING & BILLS
    # ============================================================

    async def get_shop_billing_summary(self, tenant_id: UUID | str) -> CloudShopBillingSummary:
        return await self.request(
            "GET", endpoints.shop_billing_summary_url(tenant_id), response_model=CloudShopBillingSummary
        )

    async def list_shop_bills(
        self,
        tenant_id: UUID | str,
        limit: int = 50,
        offset: int = 0,
        status: str | None = None,
        start_date: Any | None = None,
        end_date: Any | None = None,
    ) -> CloudBillListResponse:
        params = {
            "limit": limit,
            "offset": offset,
            "status": status,
            "start_date": start_date,
            "end_date": end_date,
        }
        return await self.request(
            "GET", endpoints.shop_bills_url(tenant_id), params=params, response_model=CloudBillListResponse
        )

    async def list_all_bills(
        self,
        limit: int = 50,
        offset: int = 0,
        status: str | None = None,
        start_date: Any | None = None,
        end_date: Any | None = None,
    ) -> CloudBillListResponse:
        params = {
            "limit": limit,
            "offset": offset,
            "status": status,
            "start_date": start_date,
            "end_date": end_date,
        }
        return await self.request(
            "GET", endpoints.CROSS_SHOP_BILLS, params=params, response_model=CloudBillListResponse
        )

    # ============================================================
    # SUBSCRIPTIONS
    # ============================================================

    async def list_subscriptions(
        self,
        limit: int = 50,
        offset: int = 0,
        plan: str | None = None,
        status: str | None = None,
    ) -> CloudShopSubscriptionListResponse:
        params = {"limit": limit, "offset": offset, "plan": plan, "status": status}
        return await self.request(
            "GET", endpoints.SUBSCRIPTIONS, params=params, response_model=CloudShopSubscriptionListResponse
        )

    async def get_subscription_by_id(self, subscription_id: UUID | str) -> CloudSubscriptionDetail:
        return await self.request(
            "GET", endpoints.subscription_detail_url(subscription_id), response_model=CloudSubscriptionDetail
        )

    async def get_shop_subscription(self, tenant_id: UUID | str) -> CloudSubscriptionDetail:
        return await self.request(
            "GET", endpoints.shop_subscription_url(tenant_id), response_model=CloudSubscriptionDetail
        )

    async def get_shop_subscription_history(
        self, tenant_id: UUID | str
    ) -> CloudSubscriptionHistoryResponse:
        return await self.request(
            "GET",
            endpoints.shop_subscription_history_url(tenant_id),
            response_model=CloudSubscriptionHistoryResponse,
        )

    async def activate_shop_subscription(
        self,
        tenant_id: UUID | str,
        payload: CloudSubscriptionActivationRequest,
    ) -> CloudSubscriptionActivationResponse:
        # Convert datetime fields to ISO strings for JSON
        body = payload.model_dump(mode="json")
        return await self.request(
            "POST",
            endpoints.shop_subscription_activate_url(tenant_id),
            json=body,
            response_model=CloudSubscriptionActivationResponse,
        )

    async def upgrade_shop_subscription(
        self,
        tenant_id: UUID | str,
        payload: CloudSubscriptionChangeRequest,
    ) -> CloudSubscriptionOperationResponse:
        body = payload.model_dump(mode="json")
        return await self.request(
            "POST",
            endpoints.shop_subscription_upgrade_url(tenant_id),
            json=body,
            response_model=CloudSubscriptionOperationResponse,
        )

    async def downgrade_shop_subscription(
        self,
        tenant_id: UUID | str,
        payload: CloudSubscriptionChangeRequest,
    ) -> CloudSubscriptionOperationResponse:
        body = payload.model_dump(mode="json")
        return await self.request(
            "POST",
            endpoints.shop_subscription_downgrade_url(tenant_id),
            json=body,
            response_model=CloudSubscriptionOperationResponse,
        )

    async def suspend_shop_subscription(
        self,
        tenant_id: UUID | str,
        payload: CloudSubscriptionActionRequest,
    ) -> CloudSubscriptionOperationResponse:
        body = payload.model_dump(mode="json")
        return await self.request(
            "POST",
            endpoints.shop_subscription_suspend_url(tenant_id),
            json=body,
            response_model=CloudSubscriptionOperationResponse,
        )

    async def cancel_shop_subscription(
        self,
        tenant_id: UUID | str,
        payload: CloudSubscriptionActionRequest,
    ) -> CloudSubscriptionOperationResponse:
        body = payload.model_dump(mode="json")
        return await self.request(
            "POST",
            endpoints.shop_subscription_cancel_url(tenant_id),
            json=body,
            response_model=CloudSubscriptionOperationResponse,
        )

    # ============================================================
    # AUDIT LOGS, USAGE, SUPPORT
    # ============================================================

    async def list_shop_audit_logs(
        self,
        tenant_id: UUID | str,
        limit: int = 50,
        offset: int = 0,
        action: str | None = None,
        user_id: UUID | str | None = None,
    ) -> CloudAuditLogListResponse:
        params = {"limit": limit, "offset": offset, "action": action, "user_id": user_id}
        return await self.request(
            "GET", endpoints.shop_audit_logs_url(tenant_id), params=params, response_model=CloudAuditLogListResponse
        )

    async def get_shop_usage(self, tenant_id: UUID | str) -> CloudShopUsageResponse:
        return await self.request(
            "GET", endpoints.shop_usage_url(tenant_id), response_model=CloudShopUsageResponse
        )

    async def get_shop_support(self, tenant_id: UUID | str) -> CloudSupportResponse:
        return await self.request(
            "GET", endpoints.shop_support_url(tenant_id), response_model=CloudSupportResponse
        )


# Global client instance / dependency
_default_client: ShopFlowClient | None = None


def get_shopflow_client() -> ShopFlowClient:
    """Dependency provider for ShopFlowClient."""
    global _default_client
    if _default_client is None:
        _default_client = ShopFlowClient()
    return _default_client
