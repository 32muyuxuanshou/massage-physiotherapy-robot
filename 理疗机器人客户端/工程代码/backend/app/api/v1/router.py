from fastapi import APIRouter

from app.api.v1 import auth, users, devices, ai, therapy


router = APIRouter(prefix="/v1")

router.include_router(auth.router)
router.include_router(users.router)
router.include_router(devices.router)
router.include_router(ai.router)
router.include_router(therapy.router)
