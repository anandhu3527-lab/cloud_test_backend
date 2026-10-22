from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response
from app.core.config import settings

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        response = await call_next(request)
        
        # General security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        
        # Strict Transport Security for production
        if settings.APP_ENV == "production":
            # 1 year
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
            
            # Basic Content-Security-Policy
            response.headers["Content-Security-Policy"] = "default-src 'self'; frame-ancestors 'none';"
        
        return response
