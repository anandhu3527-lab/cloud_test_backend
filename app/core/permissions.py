"""
Cloud RBAC Permission Constants.

Naming convention: RESOURCE_ACTION = "resource:action"
These constants are the single source of truth for permission strings
used in require_permission() checks and in the seed script.
"""

# Employee / User management
EMPLOYEE_CREATE = "employee:create"
EMPLOYEE_READ = "employee:read"
EMPLOYEE_UPDATE = "employee:update"
EMPLOYEE_DEACTIVATE = "employee:deactivate"

# Dashboard
DASHBOARD_VIEW = "dashboard:view"

# ShopFlow Integration
SHOPFLOW_READ = "shopflow:read"
SHOPFLOW_MANAGE = "shopflow:manage"
SHOPFLOW_SUBSCRIPTION_MANAGE = "shopflow:subscription:manage"

