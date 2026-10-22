from typing import Literal

# Environment Names
ENV_DEVELOPMENT: Literal["development"] = "development"
ENV_TESTING: Literal["testing"] = "testing"
ENV_STAGING: Literal["staging"] = "staging"
ENV_PRODUCTION: Literal["production"] = "production"
EnvironmentType = Literal["development", "testing", "staging", "production"]

# Headers
HEADER_REQUEST_ID = "X-Request-ID"

# Error Codes
ERR_VALIDATION = "VALIDATION_ERROR"
ERR_INTERNAL_SERVER = "INTERNAL_SERVER_ERROR"
ERR_CONFIGURATION = "CONFIGURATION_ERROR"
ERR_DATABASE = "DATABASE_ERROR"
ERR_AUTHENTICATION = "AUTHENTICATION_ERROR"
ERR_AUTHORIZATION = "AUTHORIZATION_ERROR"
ERR_NOT_FOUND = "NOT_FOUND_ERROR"
ERR_RATE_LIMIT = "RATE_LIMIT_ERROR"
ERR_EXTERNAL_SERVICE = "EXTERNAL_SERVICE_ERROR"
