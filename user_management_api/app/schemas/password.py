from pydantic import BaseModel, ConfigDict


class ForgotPasswordRequest(BaseModel):
    # Intentionally not strict EmailStr:
    # many orgs use internal domains (e.g. .local) that EmailStr can reject.
    email: str


class ForgotPasswordResponse(BaseModel):
    ok: bool


class ResetPasswordRequest(BaseModel):
    model_config = ConfigDict(strict=True)

    token: str
    password: str


class InspectResetRequest(BaseModel):
    model_config = ConfigDict(strict=True)

    token: str


class ResetPasswordResponse(BaseModel):
    ok: bool
