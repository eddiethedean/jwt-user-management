"""Mount bundled FastAPI routers and gateway-local routes onto ``FluxLit.api``."""

from __future__ import annotations

from fastapi import Request
from fastapi.responses import JSONResponse, Response
from fluxlit import FluxLit

from app.routes.admin import router as admin_router
from app.routes.auth import router as auth_router
from app.routes.invites import router as invites_router
from app.routes.password_reset import router as password_reset_router
from app.routes.public_urls import api_base, app_base, docs_url
from app.routes.users import router as users_router


def install_bundled_app_routes(fluxlit_app: FluxLit) -> None:
    api = fluxlit_app.api

    for router in (
        auth_router,
        admin_router,
        invites_router,
        password_reset_router,
        users_router,
    ):
        api.include_router(router)

    @api.get("/", include_in_schema=False)
    async def api_root(_request: Request) -> Response:
        return JSONResponse(
            {
                "ok": True,
                "service": "jwt_users_api",
                "docs": docs_url(_request),
            }
        )

    @api.get("/__meta", include_in_schema=False)
    async def meta(request: Request) -> JSONResponse:
        app_base_url = app_base(request)
        api_base_url = api_base(request)
        return JSONResponse(
            {
                "ok": True,
                "base_path": str(request.scope.get("root_path") or ""),
                "external_base": app_base_url,
                "external_app_base": app_base_url,
                "external_api_base": api_base_url,
            }
        )
