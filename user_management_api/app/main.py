import os

from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse

from app.core.config import settings
from app.middleware.root_path import RootPathMiddleware
from app.routes.admin import router as admin_router
from app.routes.auth import router as auth_router
from app.routes.invites import router as invites_router
from app.routes.users import router as users_router


app = FastAPI(title="User Management API")

if not (os.getenv("DISABLE_ROOT_PATH_MIDDLEWARE") or "").strip().lower() in {
    "1",
    "true",
    "yes",
    "y",
    "on",
}:
    app.add_middleware(RootPathMiddleware, base_path=settings.base_path)

app.include_router(auth_router)
app.include_router(admin_router)
app.include_router(invites_router)
app.include_router(users_router)


@app.get("/", include_in_schema=False)
def root(request: Request) -> RedirectResponse:
    bp = str(request.scope.get("root_path") or "").rstrip("/")
    return RedirectResponse(url=f"{bp}/register", status_code=302)
