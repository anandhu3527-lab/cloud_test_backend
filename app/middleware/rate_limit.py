from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from fastapi import Request, Response, FastAPI
from app.core.config import settings
from app.core.constants import ERR_RATE_LIMIT

# Initialize the limiter. We use the remote address as the key by default.
# For a production deployment behind a reverse proxy/load balancer,
# this should ideally use a forwarded IP header like X-Forwarded-For.
# SlowAPI handles this if the ProxyHeadersMiddleware is used or request.client.host is correct.
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[settings.RATE_LIMIT_DEFAULT],
    enabled=settings.RATE_LIMIT_ENABLED,
)

def _custom_rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded) -> Response:
    """
    Custom handler for rate limit exceeded exceptions to match our consistent API response format.
    """
    from fastapi.responses import JSONResponse
    
    request_id = getattr(request.state, "request_id", None)
    
    return JSONResponse(
        status_code=429,
        content={
            "success": False,
            "error": {
                "code": ERR_RATE_LIMIT,
                "message": "Rate limit exceeded"
            },
            "request_id": request_id
        }
    )

def setup_rate_limiting(app: FastAPI) -> None:
    """Configure rate limiting for the application."""
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _custom_rate_limit_exceeded_handler)
