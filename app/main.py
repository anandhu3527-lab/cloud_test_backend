from contextlib import asynccontextmanager
from typing import Any, Dict

from fastapi import FastAPI, Request, status, Depends
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
import uvicorn

from app.core.config import settings
from app.core.exceptions import AppException
from app.core.logging import setup_logging, get_logger
from app.core.constants import ERR_VALIDATION, ERR_INTERNAL_SERVER
from app.core.database import get_db, engine
from app.api.v1.router import api_router

from app.middleware.request_id import RequestIDMiddleware
from app.middleware.logging import LoggingMiddleware
from app.middleware.security_headers import SecurityHeadersMiddleware
from app.middleware.rate_limit import setup_rate_limiting, limiter

# Setup basic logging right away
setup_logging()
logger = get_logger("main")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info(f"Starting up {settings.APP_NAME} in {settings.APP_ENV} mode")
    yield
    # Shutdown
    logger.info("Shutting down")
    await engine.dispose()


def create_app() -> FastAPI:
    """Factory to create the FastAPI application."""
    
    app_kwargs = {
        "title": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "lifespan": lifespan,
    }

    # Hide docs in production
    if settings.APP_ENV == "production":
        app_kwargs.update({
            "openapi_url": None,
            "docs_url": None,
            "redoc_url": None,
        })

    app = FastAPI(**app_kwargs)

    # Add middlewares (order matters!)
    # Outer middlewares run first on request, last on response.
    
    # 1. TrustedHost
    app.add_middleware(
        TrustedHostMiddleware, 
        allowed_hosts=settings.TRUSTED_HOSTS
    )
    
    # 2. CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 3. Security Headers
    app.add_middleware(SecurityHeadersMiddleware)

    # 4. Request ID (should be early so other middlewares can use it)
    app.add_middleware(RequestIDMiddleware)
    
    # 5. Logging (after RequestID to log it)
    app.add_middleware(LoggingMiddleware)

    # Rate Limiting setup
    setup_rate_limiting(app)

    # --- Exception Handlers ---

    @app.exception_handler(AppException)
    async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
        request_id = getattr(request.state, "request_id", None)
        logger.warning(f"AppException: {exc.code} - {exc.message} (request_id={request_id})")
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "success": False,
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                },
                "request_id": request_id,
            },
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        request_id = getattr(request.state, "request_id", None)
        logger.warning(f"Validation Error: {exc.errors()} (request_id={request_id})")
        
        # In production, we might want to sanitize the details further
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "success": False,
                "error": {
                    "code": ERR_VALIDATION,
                    "message": "Invalid request parameters",
                },
                "request_id": request_id,
            },
        )

    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        request_id = getattr(request.state, "request_id", None)
        logger.error(f"Unhandled Exception: {exc} (request_id={request_id})", exc_info=True)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "success": False,
                "error": {
                    "code": ERR_INTERNAL_SERVER,
                    "message": "An unexpected error occurred.",
                },
                "request_id": request_id,
            },
        )

    # --- Endpoints ---
    app.include_router(api_router, prefix=settings.API_V1_PREFIX)

    @app.get("/health", tags=["Health"])
    @app.get(f"{settings.API_V1_PREFIX}/health", tags=["Health"])
    @limiter.limit("10/minute")
    async def health_check(request: Request, db: AsyncSession = Depends(get_db)) -> Dict[str, Any]:
        request_id = getattr(request.state, "request_id", None)
        db_status = "unhealthy"
        
        try:
            # Check DB
            await db.execute(text("SELECT 1"))
            db_status = "healthy"
        except Exception as e:
            logger.error(f"Health check DB error: {e}")
            return JSONResponse(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                content={
                    "success": False,
                    "data": {
                        "status": "unhealthy",
                        "database": "unavailable"
                    },
                    "request_id": request_id
                }
            )

        return {
            "success": True,
            "data": {
                "status": "healthy",
                "service": settings.APP_NAME,
                "version": settings.APP_VERSION,
                "database": db_status
            },
            "request_id": request_id
        }

    return app

app = create_app()

if __name__ == "__main__":
    # Convenience for running directly
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
