import string
import uuid
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response
from app.core.constants import HEADER_REQUEST_ID
from app.core.security import generate_secure_token

class RequestIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        # Check if request has a valid X-Request-ID header
        request_id = request.headers.get(HEADER_REQUEST_ID)
        
        # Validate existing request ID. We want it to be alphanumeric + hyphens
        # to prevent log injection, and of a reasonable length.
        if not request_id or not self._is_valid_request_id(request_id):
            # Generate a new safe request ID
            request_id = f"req_{uuid.uuid4().hex}"
        
        # Attach request_id to request state so other parts of the app can use it
        request.state.request_id = request_id
        
        # Call the next middleware/route handler
        response = await call_next(request)
        
        # Attach the request ID to the response header
        response.headers[HEADER_REQUEST_ID] = request_id
        
        return response

    def _is_valid_request_id(self, request_id: str) -> bool:
        """Validate an incoming request ID."""
        if len(request_id) > 100 or len(request_id) < 5:
            return False
            
        # Allow alphanumeric and common safe separators
        allowed_chars = set(string.ascii_letters + string.digits + "-_")
        if not all(c in allowed_chars for c in request_id):
            return False
            
        return True
