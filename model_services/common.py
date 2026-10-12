import secrets

from fastapi import Header, HTTPException

from app.core.config import get_settings


def require_model_key(x_model_key: str = Header("")):
    expected = get_settings().model_service_key.get_secret_value()
    if not expected or expected.startswith("CHANGE_ME"):
        raise HTTPException(503, "Configure MODEL_SERVICE_KEY")
    if not secrets.compare_digest(x_model_key, expected):
        raise HTTPException(401, "Invalid model service key")

