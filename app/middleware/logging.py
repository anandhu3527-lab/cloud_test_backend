import time
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response
from app.core.logging import get_logger

logger = get_logger("request")

class LoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        # Start timer
        start_time = time.perf_counter()
        
        request_id = getattr(request.state, "request_id", "unknown")
        
        try:
            # Process request
            response = await call_next(request)
            
            # Calculate duration
            process_time = time.perf_counter() - start_time
            duration_ms = round(process_time * 1000, 2)
            
            # Log structured access
            logger.info(
                f"request_id={request_id} "
                f"method={request.method} "
                f"path={request.url.path} "
                f"status={response.status_code} "
                f"duration_ms={duration_ms}"
            )
            
            return response
            
        except Exception as e:
            # Calculate duration even for failed requests
            process_time = time.perf_counter() - start_time
            duration_ms = round(process_time * 1000, 2)
            
            logger.error(
                f"request_id={request_id} "
                f"method={request.method} "
                f"path={request.url.path} "
                f"status=500 "
                f"duration_ms={duration_ms} "
                f"error={e.__class__.__name__}"
            )
            # Re-raise so global exception handlers can catch it
            raise
