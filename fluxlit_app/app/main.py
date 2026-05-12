from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response
from app.routes.admin import router as admin_router
from app.routes.auth import router as auth_router
from app.routes.password_reset import router as password_reset_router
from app.routes.invites import router as invites_router
from app.routes.public_urls import app_base
from app.routes.users import router as users_router

# Disable automatic slash redirects so mounted sub-apps (e.g. Streamlit at /app)
# can control their own trailing-slash behavior without redirect loops.
app = FastAPI(title="User Management API", redirect_slashes=False)

## Legacy HTML UI assets were archived; no static mount needed.


app.include_router(auth_router)
app.include_router(admin_router)
app.include_router(invites_router)
app.include_router(password_reset_router)
app.include_router(users_router)


@app.get("/__meta", include_in_schema=False)
async def meta(request: Request) -> JSONResponse:
    """
    Small metadata endpoint intended for the mounted Streamlit UI.

    It returns the externally-visible base URL from the ASGI request/root path.
    The FluxLit gateway path uses the richer native ``FluxLit.urls`` helpers.
    """

    bp = str(request.scope.get("root_path") or "")
    api_base = app_base(request)
    return JSONResponse(
        {
            "ok": True,
            "base_path": bp,
            "external_base": api_base,
            "external_app_base": api_base,
            "external_api_base": api_base,
        }
    )


@app.get("/", include_in_schema=False)
async def root(request: Request) -> Response:
    return JSONResponse({"ok": True, "service": "jwt_users_api", "docs": "/docs"})
