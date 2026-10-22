"""
Aggregated router for ShopFlow integration endpoints.
"""

from fastapi import APIRouter

from app.api.v1.shopflow.activity import router as activity_router
from app.api.v1.shopflow.alerts import router as alerts_router
from app.api.v1.shopflow.audit import router as audit_router
from app.api.v1.shopflow.billing import router as billing_router
from app.api.v1.shopflow.customers import router as customers_router
from app.api.v1.shopflow.features import router as features_router
from app.api.v1.shopflow.health import router as health_router
from app.api.v1.shopflow.kadan import router as kadan_router
from app.api.v1.shopflow.overview import router as overview_router
from app.api.v1.shopflow.products import router as products_router
from app.api.v1.shopflow.revenue import router as revenue_router
from app.api.v1.shopflow.shops import router as shops_router
from app.api.v1.shopflow.subscriptions import router as subscriptions_router
from app.api.v1.shopflow.support import router as support_router
from app.api.v1.shopflow.system_health import router as system_health_router
from app.api.v1.shopflow.usage import router as usage_router
from app.api.v1.shopflow.users import router as users_router

router = APIRouter()

# Health & Overview
router.include_router(overview_router)
router.include_router(health_router)
router.include_router(system_health_router)

# Shops & Activity
router.include_router(shops_router)
router.include_router(activity_router)

# Shop Resources
router.include_router(users_router)
router.include_router(products_router)
router.include_router(customers_router)
router.include_router(billing_router)
router.include_router(revenue_router)
router.include_router(subscriptions_router)
router.include_router(audit_router)
router.include_router(usage_router)
router.include_router(support_router)
router.include_router(kadan_router)
router.include_router(alerts_router)
router.include_router(features_router)
