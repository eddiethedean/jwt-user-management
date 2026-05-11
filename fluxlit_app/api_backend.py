"""Mount bundled FastAPI routers and gateway-local routes onto ``FluxLit.api``."""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response
from fastapi_workbench import base_path as wb_base_path, external_base

from app.routes.admin import router as admin_router
from app.routes.auth import router as auth_router
from app.routes.invites import router as invites_router
from app.routes.password_reset import router as password_reset_router
from app.routes.users import router as users_router

from cookie_debug_middleware import attach_cookie_debug_middleware


def install_bundled_app_routes(api: FastAPI) -> None:
    for router in (
        auth_router,
        admin_router,
        invites_router,
        password_reset_router,
        users_router,
    ):
        api.include_router(router)

    attach_cookie_debug_middleware(api)

    @api.get("/", include_in_schema=False)
    async def api_root(_request: Request) -> Response:
        return JSONResponse(
            {
                "ok": True,
                "service": "jwt_users_api",
                "docs": "/api/docs",
            }
        )

    @api.get("/__meta", include_in_schema=False)
    async def meta(request: Request) -> JSONResponse:
        bp = wb_base_path(request)
        return JSONResponse(
            {
                "ok": True,
                "base_path": bp,
                "external_base": external_base(request),
                "external_api_base": external_base(request) + (bp or ""),
            }
        )
