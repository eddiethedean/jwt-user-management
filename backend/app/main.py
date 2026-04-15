from fastapi import FastAPI

from app.api.routes_auth import router as auth_router
from app.api.routes_invites import router as invites_router
from app.api.routes_password import router as password_router
from app.api.routes_users import router as users_router


app = FastAPI(title="JWT User Management API")


app.include_router(auth_router)
app.include_router(users_router)
app.include_router(invites_router)
app.include_router(password_router)
