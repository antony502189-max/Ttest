from typing import Annotated, Literal
from uuid import UUID

from email_validator import EmailNotValidError, validate_email
from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, WithJsonSchema, model_validator

from ..core.config import get_settings


def validate_application_email(value: object) -> str:
    if not isinstance(value, str):
        raise ValueError("Email must be a string")
    try:
        result = validate_email(
            value,
            check_deliverability=False,
            test_environment=get_settings().app_env == "test",
        )
    except EmailNotValidError as error:
        raise ValueError(str(error)) from error
    return result.normalized


ApplicationEmail = Annotated[
    str,
    BeforeValidator(validate_application_email),
    WithJsonSchema({"type": "string", "format": "email"}),
]


class RegisterRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(min_length=2, max_length=120)
    email: ApplicationEmail
    password: str = Field(min_length=12, max_length=256)
    role: Literal["tenant", "host"] = "tenant"


class LoginRequest(BaseModel):
    email: ApplicationEmail
    password: str


class GoogleLoginRequest(BaseModel):
    credential: str = Field(min_length=20, max_length=10_000)


class ForgotPasswordRequest(BaseModel):
    email: ApplicationEmail


class ResetPasswordRequest(BaseModel):
    token: str = Field(min_length=32, max_length=512)
    password: str = Field(min_length=12, max_length=256)


class VerifyEmailRequest(BaseModel):
    token: str = Field(min_length=32, max_length=512)


class UserResponse(BaseModel):
    id: str
    name: str
    email: ApplicationEmail
    role: str
    phone: str
    whatsapp: str
    telegram: str
    about: str
    initials: str
    showPhone: bool
    showWhatsApp: bool
    allowContactForm: bool
    avatarUrl: str | None = None


class UserUpdateRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str | None = Field(default=None, min_length=2, max_length=120)
    phone: str | None = Field(default=None, max_length=64)
    whatsapp: str | None = Field(default=None, max_length=64)
    telegram: str | None = Field(default=None, max_length=64)
    about: str | None = Field(default=None, max_length=4_000)
    showPhone: bool | None = None
    showWhatsApp: bool | None = None
    allowContactForm: bool | None = None

    @model_validator(mode="after")
    def reject_explicit_nulls(self):
        for field in self.model_fields_set:
            if getattr(self, field) is None:
                raise ValueError(f"{field} cannot be null")
        return self


class AvatarUpdateRequest(BaseModel):
    assetId: UUID | None = None
