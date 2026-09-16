from fastapi import APIRouter

from .api_acls import router as acls_router
from .api_commands import router as commands_router
from .api_devices import router as devices_router
from .api_tokens import router as tokens_router

router = APIRouter(prefix="/api/control", tags=["control-plane"])
router.include_router(commands_router)
router.include_router(devices_router)
router.include_router(tokens_router)
router.include_router(acls_router)
