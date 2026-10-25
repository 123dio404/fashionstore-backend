from fastapi import APIRouter
from app.api.v1 import (
    ai_reports,
    auth,
    branches,
    commerce,
    customer_experience,
    exchanges,
    finance,
    inventory,
    marketing,
    ml,
    operations,
    products,
    reports,
    saas,
    suppliers,
    sync,
    users,
)

api_router = APIRouter(prefix='/api/v1')
api_router.include_router(auth.router)
api_router.include_router(saas.router)
api_router.include_router(sync.router)
api_router.include_router(exchanges.router)
api_router.include_router(ml.router)
api_router.include_router(ai_reports.router)
api_router.include_router(users.router)
api_router.include_router(branches.router)
api_router.include_router(products.router)
api_router.include_router(suppliers.router)
api_router.include_router(inventory.router)
api_router.include_router(finance.router)
api_router.include_router(operations.router)
api_router.include_router(commerce.router)
api_router.include_router(customer_experience.router)
api_router.include_router(marketing.router)
api_router.include_router(reports.router)
router = api_router

