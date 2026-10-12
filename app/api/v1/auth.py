from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select

from app.api.dependencies import current_principal, get_session, get_settings_dependency
from app.core.exceptions import AppError
from app.db.models import Tenant, User
from app.security.authentication import issue_token, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tenant_name: str = Field(min_length=1, max_length=120)
    username: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=1, max_length=256)


@router.post("/login")
def login(body: LoginRequest, session=Depends(get_session), settings=Depends(get_settings_dependency)):
    tenant = session.scalar(select(Tenant).where(Tenant.name == body.tenant_name))
    user = session.scalar(select(User).where(
        User.tenant_id == tenant.id, User.username == body.username,
    )) if tenant else None
    valid = verify_password(body.password, user.password_hash if user else None)
    if not valid or not user or not user.is_active:
        raise AppError("INVALID_CREDENTIALS", "租户、用户名或密码不正确", 401)
    return {"access_token": issue_token(user, settings), "token_type": "bearer"}


@router.get("/me")
def me(principal=Depends(current_principal)):
    return {"user_id": principal.user_id, "tenant_id": principal.tenant_id, "role": principal.role}

