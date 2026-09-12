from fastapi import APIRouter
from app.api.v1 import auth, branches, finance, inventory, operations, products, suppliers, users
api_router = APIRouter(prefix='/api/v1')
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(branches.router)
api_router.include_router(products.router)
api_router.include_router(suppliers.router)
api_router.include_router(inventory.router)
api_router.include_router(finance.router)
api_router.include_router(operations.router)
router = api_router
