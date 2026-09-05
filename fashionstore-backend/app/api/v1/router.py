from fastapi import APIRouter
from app.api.v1 import auth, branches, inventory, products, suppliers, users
api_router = APIRouter(prefix='/api/v1')
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(branches.router)
api_router.include_router(products.router)
api_router.include_router(suppliers.router)
api_router.include_router(inventory.router)
router = api_router
