from fastapi import FastAPI
from fastapi.responses import RedirectResponse

from app.routes.auth import router as auth_router
from app.routes.users import router as users_router


app = FastAPI(title="User Management API")

app.include_router(auth_router)
app.include_router(users_router)


@app.get("/", include_in_schema=False)
def root() -> RedirectResponse:
    return RedirectResponse(url="/register", status_code=302)
