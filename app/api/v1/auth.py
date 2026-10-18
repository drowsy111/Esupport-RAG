"""
文件说明: 该模块定义了FastAPI应用的认证相关路由，包括登录和获取当前用户信息。
"""
from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select

from app.api.dependencies import current_principal, get_session, get_settings_dependency
from app.core.exceptions import AppError
from app.db.models import Tenant, User
from app.security.authentication import issue_token, verify_password

"""
登录请求模型定义
APIRouter实例化，用于定义认证相关的路由。
"""
router = APIRouter(prefix="/auth", tags=["认证授权"])


class LoginRequest(BaseModel):
    """
    登录请求模型
    包含租户名称、用户名和密码的登录请求数据模型。
    ConfigDict: Pydantic模型的全局配置字典。extra="forbid": 禁止额外的未定义字段。
    Attributes:
        tenant_name (str): 租户名称，长度在1到120个字符之间。
        username (str): 用户名，长度在1到100个字符之间。
        password (str): 密码，长度在1到256个字符之间。
    """
    model_config = ConfigDict(extra="forbid")
    tenant_name: str = Field(min_length=1, max_length=120)
    username: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=1, max_length=256)


@router.post("/login")
def login(body: LoginRequest, session=Depends(get_session), settings=Depends(get_settings_dependency)):
    """
    函数说明: 验证用户的登录信息并返回访问令牌。
    Args:
        body (LoginRequest): 登录请求体，包含租户名称、用户名和密码。
        session: 数据库会话依赖。(框架自动注入)
        settings: 配置对象/应用设置依赖。(框架自动注入)

    Returns:
        dict: 包含访问令牌和令牌类型的字典。
    """
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
    """
    获取当前登录用户的信息。控制客户端用户逻辑的访问权限，包括数据库访问权限，界面显示等。

    Args:
        principal: 当前请求的主体信息，由依赖项current_principal提供。

    Returns:
        dict: 包含用户ID、租户ID和角色信息的字典。
    """
    return {"user_id": principal.user_id, "tenant_id": principal.tenant_id, "role": principal.role}

