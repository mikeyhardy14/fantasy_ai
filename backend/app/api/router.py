from fastapi import APIRouter

from app.api.routes import ai, auth, integrations, leagues, misc

api_router = APIRouter(prefix="/api")
api_router.include_router(misc.router)
api_router.include_router(auth.router)
api_router.include_router(integrations.router)
api_router.include_router(leagues.router)
api_router.include_router(ai.router)
