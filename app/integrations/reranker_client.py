import math

import httpx

from app.core.exceptions import AppError


class RerankerClient:
    def __init__(self, settings):
        self.settings = settings

    def score(self, query: str, texts: list[str]) -> list[float]:
        try:
            response = httpx.post(
                self.settings.reranker_url.rstrip("/") + "/rerank",
                headers={"X-Model-Key": self.settings.model_service_key.get_secret_value()},
                json={"query": query, "texts": texts},
                timeout=self.settings.external_timeout_seconds,
            )
            response.raise_for_status()
            scores = [float(x) for x in response.json()["scores"]]
            if len(scores) != len(texts) or not all(math.isfinite(x) for x in scores):
                raise ValueError("invalid reranker scores")
            return scores
        except Exception as exc:
            raise AppError("RERANKER_UNAVAILABLE", "精排服务不可用", 503) from exc

