import httpx
import pytest

from app.core.config import Settings
from app.core.exceptions import AppError
from app.integrations.embedding_client import EmbeddingClient
from app.integrations.llm_gateway import LLMGateway
from app.integrations.reranker_client import RerankerClient
from app.schemas.query_plan import QueryPlan


def llm_gateway():
    return LLMGateway(Settings(
        _env_file=None, llm_base_url="https://api.deepseek.com",
        llm_model="deepseek-flash", llm_api_key="test-secret",
    ))


def llm_response(status=200, json_body=None):
    request = httpx.Request("POST", "https://api.deepseek.com/chat/completions")
    return httpx.Response(status, json=json_body, request=request)


def test_llm_gateway_returns_validated_json_response(monkeypatch):
    monkeypatch.setattr(httpx, "post", lambda *a, **kw: llm_response(json_body={
        "choices": [{"message": {"content": (
            '{"status":"answered","claims":[{"text":"Supported","citation_ids":["c1"]}]}'
        )}}],
    }))

    result = llm_gateway().generate("question", [{"id": "c1", "text": "evidence"}])

    assert result.status == "answered"
    assert result.claims[0].citation_ids == ["c1"]


def test_llm_gateway_returns_validated_query_plan_and_context(monkeypatch):
    requests = []
    timeouts = []

    def respond(*args, **kwargs):
        requests.append(kwargs["json"])
        timeouts.append(kwargs["timeout"])
        return llm_response(json_body={
            "choices": [{"message": {"content": (
                '{"route":"decompose","sub_queries":["检查配置","验证状态"],'
                '"clarification_message":""}'
            )}}],
        })

    monkeypatch.setattr(httpx, "post", respond)

    result = llm_gateway().plan_query(
        "检查配置并验证状态", history=[{"role": "user", "content": "升级"}],
        context={"product_version": "2.4.1"}, request_id="plan-123",
    )

    assert result == QueryPlan(
        route="decompose", sub_queries=["检查配置", "验证状态"],
    )
    assert requests[0]["messages"][1]["content"] == (
        '{"query": "检查配置并验证状态", "history": '
        '[{"role": "user", "content": "升级"}], "context": {"product_version": "2.4.1"}}'
    )
    assert requests[0]["max_tokens"] <= 512
    assert timeouts == [20]


def test_llm_gateway_rejects_invalid_query_plan(monkeypatch):
    monkeypatch.setattr(httpx, "post", lambda *a, **kw: llm_response(json_body={
        "choices": [{"message": {"content": (
            '{"route":"decompose","sub_queries":["only one"],"clarification_message":""}'
        )}}],
    }))

    with pytest.raises(AppError) as error:
        llm_gateway().plan_query("composite question")

    assert error.value.code == "LLM_QUERY_PLAN_INVALID"


def test_llm_gateway_logs_request_id_and_completion_diagnostics(monkeypatch, caplog):
    monkeypatch.setattr(httpx, "post", lambda *a, **kw: llm_response(json_body={
        "choices": [{
            "finish_reason": "length",
            "message": {"content": '{"status":"answered"'},
        }],
        "usage": {"completion_tokens": 1800},
    }))

    with pytest.raises(AppError) as error:
        llm_gateway().generate("question", [], request_id="request-123")

    assert error.value.code == "LLM_OUTPUT_TRUNCATED"
    assert "request_id=request-123" in caplog.text
    assert "finish_reason=length" in caplog.text
    assert "completion_tokens=1800" in caplog.text
    assert '{"status":"answered"' not in caplog.text


@pytest.mark.parametrize(("status", "code", "http_status"), [
    (401, "LLM_AUTH_FAILED", 502),
    (403, "LLM_AUTH_FAILED", 502),
    (429, "LLM_RATE_LIMITED", 503),
    (408, "LLM_TIMEOUT", 504),
    (400, "LLM_REQUEST_REJECTED", 502),
    (500, "LLM_UNAVAILABLE", 503),
])
def test_llm_gateway_classifies_provider_http_errors(monkeypatch, status, code, http_status):
    monkeypatch.setattr(httpx, "post", lambda *a, **kw: llm_response(status=status))

    with pytest.raises(AppError) as error:
        llm_gateway().generate("question", [])

    assert (error.value.code, error.value.status) == (code, http_status)


def test_llm_gateway_classifies_timeouts_without_exposing_exception(monkeypatch, caplog):
    def timeout(*args, **kwargs):
        raise httpx.ReadTimeout("contains-sensitive-request-details")

    monkeypatch.setattr(httpx, "post", timeout)

    with pytest.raises(AppError) as error:
        llm_gateway().generate("question", [])

    assert (error.value.code, error.value.status) == ("LLM_TIMEOUT", 504)
    assert "contains-sensitive-request-details" not in caplog.text


def test_llm_gateway_classifies_network_errors(monkeypatch):
    def network_error(*args, **kwargs):
        raise httpx.ConnectError("connection failed")

    monkeypatch.setattr(httpx, "post", network_error)

    with pytest.raises(AppError) as error:
        llm_gateway().generate("question", [])

    assert (error.value.code, error.value.status) == ("LLM_UNAVAILABLE", 503)


@pytest.mark.parametrize(("content", "code"), [
    ("", "LLM_EMPTY_RESPONSE"),
    ("not json", "LLM_INVALID_JSON"),
    ('{"status":"unknown","claims":[]}', "LLM_SCHEMA_INVALID"),
    ('{"status":"answered","claims":[]}', "LLM_SCHEMA_INVALID"),
])
def test_llm_gateway_classifies_invalid_model_content(monkeypatch, content, code):
    monkeypatch.setattr(httpx, "post", lambda *a, **kw: llm_response(json_body={
        "choices": [{"message": {"content": content}}],
    }))

    with pytest.raises(AppError) as error:
        llm_gateway().generate("question", [])

    assert (error.value.code, error.value.status) == (code, 502)


@pytest.mark.parametrize(("payload", "code"), [
    ({"error": "bad"}, "LLM_PROVIDER_RESPONSE_INVALID"),
    ({"choices": [{"message": {"content": ""}, "finish_reason": "stop"}]},
     "LLM_EMPTY_RESPONSE"),
    ({"choices": [{"message": {"content": ""}, "finish_reason": "content_filter"}]},
     "LLM_OUTPUT_BLOCKED"),
])
def test_llm_gateway_classifies_unexpected_provider_payload(monkeypatch, payload, code):
    monkeypatch.setattr(httpx, "post", lambda *a, **kw: llm_response(json_body=payload))

    with pytest.raises(AppError) as error:
        llm_gateway().generate("question", [])

    assert error.value.code == code


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
