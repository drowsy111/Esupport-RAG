import httpx
import pytest

from app.core.config import Settings
from app.core.exceptions import AppError
from app.integrations.embedding_client import EmbeddingClient
from app.integrations.reranker_client import RerankerClient


def test_embedding_contract_rejects_wrong_model_version(monkeypatch):
    def handler(request):
        return httpx.Response(200, json={"embedding_version": "other", "items": []})

    original_client = httpx.Client
    monkeypatch.setattr(httpx, "Client", lambda **kw: original_client(
        transport=httpx.MockTransport(handler), **kw,
    ))
    with pytest.raises(AppError) as error:
        EmbeddingClient(Settings(_env_file=None)).encode(["hello"])
    assert error.value.code == "MODEL_VERSION_MISMATCH"


def test_embedding_contract_validates_dimensions(monkeypatch):
    def handler(request):
        return httpx.Response(200, json={
            "embedding_version": "bge-m3-initial",
            "items": [{"dense": [1, 2], "sparse": {"10": 1}}],
        })

    original_client = httpx.Client
    monkeypatch.setattr(httpx, "Client", lambda **kw: original_client(
        transport=httpx.MockTransport(handler), **kw,
    ))
    with pytest.raises(AppError) as error:
        EmbeddingClient(Settings(_env_file=None)).encode(["hello"])
    assert error.value.code == "EMBEDDING_UNAVAILABLE"


def test_reranker_does_not_accept_missing_scores(monkeypatch):
    monkeypatch.setattr(httpx, "post", lambda *a, **kw: httpx.Response(
        200, json={"scores": [0.9]}, request=httpx.Request("POST", "http://test/rerank"),
    ))
    with pytest.raises(AppError) as error:
        RerankerClient(Settings(_env_file=None)).score("query", ["one", "two"])
    assert error.value.code == "RERANKER_UNAVAILABLE"

