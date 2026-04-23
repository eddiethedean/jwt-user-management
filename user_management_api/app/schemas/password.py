from pydantic import BaseModel


class ForgotPasswordRequest(BaseModel):
    # Intentionally not strict EmailStr:
    # many orgs use internal domains (e.g. .local) that EmailStr can reject.
    email: str


class ForgotPasswordResponse(BaseModel):
    ok: bool


class ResetPasswordRequest(BaseModel):
    token: str
    password: str


class ResetPasswordResponse(BaseModel):
    ok: bool
