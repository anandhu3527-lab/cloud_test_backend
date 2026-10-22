"""
ShopFlow internal endpoint paths.
Verified against ShopFlow internal API exposed under /api/v1/internal/cloud.
"""

from uuid import UUID

INTERNAL_CLOUD_PREFIX = "/api/v1/internal/cloud"

# Overview Dashboard
OVERVIEW = f"{INTERNAL_CLOUD_PREFIX}/overview"
OVERVIEW_HEALTH = f"{INTERNAL_CLOUD_PREFIX}/overview/health"
OVERVIEW_SUBSCRIPTIONS = f"{INTERNAL_CLOUD_PREFIX}/overview/subscriptions"
OVERVIEW_BILLS = f"{INTERNAL_CLOUD_PREFIX}/overview/bills"

# Shop Management
SHOPS = f"{INTERNAL_CLOUD_PREFIX}/shops"
SHOPS_WITHOUT_SUBSCRIPTION = f"{INTERNAL_CLOUD_PREFIX}/shops/without-subscription"


def shop_detail_url(tenant_id: UUID | str) -> str:
    return f"{INTERNAL_CLOUD_PREFIX}/shops/{tenant_id}"


def shop_overview_url(tenant_id: UUID | str) -> str:
    return f"{INTERNAL_CLOUD_PREFIX}/shops/{tenant_id}/overview"


def shop_activity_url(tenant_id: UUID | str) -> str:
    return f"{INTERNAL_CLOUD_PREFIX}/shops/{tenant_id}/activity"


def shop_status_url(tenant_id: UUID | str) -> str:
    return f"{INTERNAL_CLOUD_PREFIX}/shops/{tenant_id}/status"


# Shop User Management
def shop_users_url(tenant_id: UUID | str) -> str:
    return f"{INTERNAL_CLOUD_PREFIX}/shops/{tenant_id}/users"


def shop_user_detail_url(tenant_id: UUID | str, user_id: UUID | str) -> str:
    return f"{INTERNAL_CLOUD_PREFIX}/shops/{tenant_id}/users/{user_id}"


def shop_user_status_url(tenant_id: UUID | str, user_id: UUID | str) -> str:
    return f"{INTERNAL_CLOUD_PREFIX}/shops/{tenant_id}/users/{user_id}/status"


def shop_user_access_reset_url(tenant_id: UUID | str, user_id: UUID | str) -> str:
    return f"{INTERNAL_CLOUD_PREFIX}/shops/{tenant_id}/users/{user_id}/access-reset"


def shop_user_activity_url(tenant_id: UUID | str, user_id: UUID | str) -> str:
    return f"{INTERNAL_CLOUD_PREFIX}/shops/{tenant_id}/users/{user_id}/activity"


# Products & Inventory
def shop_products_url(tenant_id: UUID | str) -> str:
    return f"{INTERNAL_CLOUD_PREFIX}/shops/{tenant_id}/products"


def shop_stock_summary_url(tenant_id: UUID | str) -> str:
    return f"{INTERNAL_CLOUD_PREFIX}/shops/{tenant_id}/products/stock/summary"


def shop_product_usage_url(tenant_id: UUID | str) -> str:
    return f"{INTERNAL_CLOUD_PREFIX}/shops/{tenant_id}/products/usage"


def shop_product_detail_url(tenant_id: UUID | str, product_id: UUID | str) -> str:
    return f"{INTERNAL_CLOUD_PREFIX}/shops/{tenant_id}/products/{product_id}"


def shop_product_variants_url(tenant_id: UUID | str, product_id: UUID | str) -> str:
    return f"{INTERNAL_CLOUD_PREFIX}/shops/{tenant_id}/products/{product_id}/variants"


# Customers
def shop_customers_url(tenant_id: UUID | str) -> str:
    return f"{INTERNAL_CLOUD_PREFIX}/shops/{tenant_id}/customers"


# Billing & Bills
def shop_billing_summary_url(tenant_id: UUID | str) -> str:
    return f"{INTERNAL_CLOUD_PREFIX}/shops/{tenant_id}/billing/summary"


def shop_bills_url(tenant_id: UUID | str) -> str:
    return f"{INTERNAL_CLOUD_PREFIX}/shops/{tenant_id}/billing/bills"


CROSS_SHOP_BILLS = f"{INTERNAL_CLOUD_PREFIX}/billing/bills"


# Subscriptions
SUBSCRIPTIONS = f"{INTERNAL_CLOUD_PREFIX}/subscriptions"


def subscription_detail_url(subscription_id: UUID | str) -> str:
    return f"{INTERNAL_CLOUD_PREFIX}/subscriptions/{subscription_id}"


def shop_subscription_url(tenant_id: UUID | str) -> str:
    return f"{INTERNAL_CLOUD_PREFIX}/shops/{tenant_id}/subscription"


def shop_subscription_history_url(tenant_id: UUID | str) -> str:
    return f"{INTERNAL_CLOUD_PREFIX}/shops/{tenant_id}/subscription/history"


def shop_subscription_activate_url(tenant_id: UUID | str) -> str:
    return f"{INTERNAL_CLOUD_PREFIX}/shops/{tenant_id}/subscription/activate"


def shop_subscription_upgrade_url(tenant_id: UUID | str) -> str:
    return f"{INTERNAL_CLOUD_PREFIX}/shops/{tenant_id}/subscription/upgrade"


def shop_subscription_downgrade_url(tenant_id: UUID | str) -> str:
    return f"{INTERNAL_CLOUD_PREFIX}/shops/{tenant_id}/subscription/downgrade"


def shop_subscription_suspend_url(tenant_id: UUID | str) -> str:
    return f"{INTERNAL_CLOUD_PREFIX}/shops/{tenant_id}/subscription/suspend"


def shop_subscription_cancel_url(tenant_id: UUID | str) -> str:
    return f"{INTERNAL_CLOUD_PREFIX}/shops/{tenant_id}/subscription/cancel"


# Audit Logs, Usage, Support
def shop_audit_logs_url(tenant_id: UUID | str) -> str:
    return f"{INTERNAL_CLOUD_PREFIX}/shops/{tenant_id}/audit-logs"


def shop_usage_url(tenant_id: UUID | str) -> str:
    return f"{INTERNAL_CLOUD_PREFIX}/shops/{tenant_id}/usage"


def shop_support_url(tenant_id: UUID | str) -> str:
    return f"{INTERNAL_CLOUD_PREFIX}/shops/{tenant_id}/support"
