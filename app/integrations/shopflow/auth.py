"""
Authentication helpers for ShopFlow internal service communication.
"""

from app.core.config import settings
from app.integrations.shopflow.exceptions import ShopFlowNotConfiguredError

SHOPFLOW_SERVICE_TOKEN_HEADER = "X-Cryvex-Cloud-Service-Token"


def get_service_headers(token: str | None = None) -> dict[str, str]:
    """
    Construct headers for authenticated server-to-server calls to ShopFlow.

    Security rules:
    - Dedicated service token check only.
    - Fails closed if the service token is missing or empty.
    - Never expose service token to the frontend or browser.
    """
    effective_token = token if token is not None else settings.SHOPFLOW_SERVICE_TOKEN
    
    if not effective_token or not effective_token.strip():
        raise ShopFlowNotConfiguredError(
            "ShopFlow internal service token is not configured on this CRYVEX Cloud backend."
        )

    return {
        SHOPFLOW_SERVICE_TOKEN_HEADER: effective_token.strip(),
        "Accept": "application/json",
    }
