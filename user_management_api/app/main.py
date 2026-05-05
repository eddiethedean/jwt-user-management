from fastapi import FastAPI, Request
from fastapi.responses import Response

from fastapi_workbench import safe_redirect
from app.routes.admin import router as admin_router
from app.routes.auth import router as auth_router
from app.routes.password_reset import router as password_reset_router
from app.routes.invites import router as invites_router
from app.routes.users import router as users_router


app = FastAPI(title="User Management API")

app.include_router(auth_router)
app.include_router(admin_router)
app.include_router(invites_router)
app.include_router(password_reset_router)
app.include_router(users_router)


@app.get("/", include_in_schema=False)
async def root(request: Request) -> Response:
    return safe_redirect(request, "/register", status_code=302)
