from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator


class RegisterRequest(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    password: str = Field(min_length=12, max_length=256)
    role: Literal["tenant", "host"] = "tenant"

    @field_validator("name", "email", "role", mode="before")
    @classmethod
    def strip_identity_fields(cls, value):
        return value.strip() if isinstance(value, str) else value

    @field_validator("password")
    @classmethod
    def preserve_password_whitespace(cls, value: str) -> str:
        # Passwords are opaque secrets: validate surrounding whitespace without
        # mutating it, otherwise registration and login disagree about the secret.
        if len(value.strip()) < 12:
            raise ValueError("Password must be at least 12 characters excluding surrounding whitespace")
        return value


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=256)


class GoogleLoginRequest(BaseModel):
    credential: str = Field(min_length=20, max_length=10_000)


class GoogleRoleRequest(BaseModel):
    role: Literal["tenant", "host"]


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str = Field(min_length=32, max_length=512)
    password: str = Field(min_length=12, max_length=256)

    @field_validator("password")
    @classmethod
    def preserve_password_whitespace(cls, value: str) -> str:
        if len(value.strip()) < 12:
            raise ValueError("Password must be at least 12 characters excluding surrounding whitespace")
        return value


class VerifyEmailRequest(BaseModel):
    code: str = Field(pattern=r"^\d{6}$")


class UserResponse(BaseModel):
    id: str
    name: str
    email: EmailStr
    role: str
    phone: str
    whatsapp: str
    telegram: str
    about: str
    initials: str
    showPhone: bool
    showWhatsApp: bool
    emailVerified: bool
    avatarUrl: str | None = None


class UserUpdateRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    name: str | None = Field(default=None, min_length=2, max_length=120)
    phone: str | None = Field(default=None, max_length=64)
    whatsapp: str | None = Field(default=None, max_length=64)
    telegram: str | None = Field(default=None, max_length=64)
    about: str | None = Field(default=None, max_length=4_000)
    showPhone: bool | None = None
    showWhatsApp: bool | None = None

    @model_validator(mode="after")
    def reject_explicit_nulls(self):
        for field in self.model_fields_set:
            if getattr(self, field) is None:
                raise ValueError(f"{field} cannot be null")
        return self


class AvatarUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    assetId: UUID | None = None
