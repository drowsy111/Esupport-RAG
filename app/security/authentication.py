"""
文件说明: 该模块定义了密码哈希、验证以及JWT令牌字符串的生成和解析相关的安全功能。
"""
from datetime import datetime, timedelta, timezone

import jwt

# Argon2 是目前公认最安全的密码哈希算法之一
from argon2 import PasswordHasher
from argon2.exceptions import VerificationError

from app.core.exceptions import AppError

# Argon2 密码哈希器实例
_hasher = PasswordHasher()
# dummy-login-timing-password 防御“计时攻击”
_dummy_hash = _hasher.hash("dummy-login-timing-password") 


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, hashed: str | None) -> bool:
    """
    hashed = user.password_hash if user else None
    _hasher.verify:
        用于验证输入的密码是否与存储的哈希值匹配。
    hashed or _dummy_hash:
        无论用户存不存在，都要花一次哈希计算的时间，响应时间一致，攻击者就无法通过计时差来判断用户名是否有效。
    password哈希化原理:
        从hashed中提取盐值和哈希参数,然后对输入的password进行相同的哈希计,最后比较结果是否一致。
    """
    try:
        valid = _hasher.verify(hashed or _dummy_hash, password)
        return valid and hashed is not None
    except (VerificationError, ValueError):
        return False


def issue_token(user, settings) -> str:
    """
    签发 JWT 的函数,生成JWT令牌字符串。

    JWT 规范(RFC 7519)定义的标准声明:
    sub(主体):token属于哪个用户。之后验证时靠它查用户
    iat(签发时间): 签发时间，可用来判断 token 是否太旧。
    exp(过期时间): 最重要的安全字段。过期后 token 自动失效。
    iss(签发者): 验证时检查“是不是我签的”。
    aud(受众): 验证时检查“这个 token 是不是给我的 API 用的”。

    user: 用户对象,必须包含id和tenant_id属性。
    settings: 配置对象,必须包含token_minutes和jwt_secret属性。
    返回值: JWT令牌字符串。
    """
    now = datetime.now(timezone.utc)
    return jwt.encode({
        "sub": user.id, "tenant_id": user.tenant_id,
        "iat": now, "exp": now + timedelta(minutes=settings.token_minutes),
        "iss": "enterprise-support-rag", "aud": "rag-api",
    }, settings.jwt_secret.get_secret_value(), algorithm="HS256")


def decode_token(token: str, settings) -> dict:
    """
    解析 JWT 令牌字符串，返回其中的声明(claims)字典。

    token: JWT 令牌字符串。
    settings: 配置对象，必须包含jwt_secret属性。

    返回值: 包含JWT声明的字典。
    """
    try:
        return jwt.decode(
            token, settings.jwt_secret.get_secret_value(), algorithms=["HS256"],
            issuer="enterprise-support-rag", audience="rag-api",
            options={"require": ["exp", "iat", "sub", "tenant_id"]},
        )
    except jwt.InvalidTokenError as exc:
        raise AppError("UNAUTHORIZED", "身份无效或已过期", 401) from exc
