import httpx

from app.core.exceptions import AppError
from app.schemas.embedding import EmbeddingItem


class EmbeddingClient:
    def __init__(self, settings):
        self.settings = settings

    def encode(self, texts: list[str], kind: str = "documents") -> list[EmbeddingItem]:
        items = []
        try:
            with httpx.Client(
                timeout=self.settings.external_timeout_seconds,
                headers={"X-Model-Key": self.settings.model_service_key.get_secret_value()},
            ) as client:
                for offset in range(0, len(texts), 16):
                    response = client.post(
                        self.settings.embedding_url.rstrip("/") + f"/embed/{kind}",
                        json={"texts": texts[offset:offset + 16]},
                    )
                    response.raise_for_status()
                    payload = response.json()
                    if payload["embedding_version"] != self.settings.embedding_version:
                        raise AppError("MODEL_VERSION_MISMATCH", "编码服务版本不匹配", 503)
                    batch = [EmbeddingItem.model_validate(x) for x in payload["items"]]
                    if len(batch) != len(texts[offset:offset + 16]):
                        raise ValueError("embedding count mismatch")
                    items.extend(batch)
        except AppError:
            raise
        except Exception as exc:
            raise AppError("EMBEDDING_UNAVAILABLE", "向量编码服务不可用", 503) from exc
        return items

