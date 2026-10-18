import json
import logging
from pathlib import Path
from typing import NoReturn

import httpx
from pydantic import ValidationError

from app.core.exceptions import AppError
from app.schemas.chat import GeneratedAnswer
from app.schemas.query_plan import QueryPlan

logger = logging.getLogger(__name__)
PROMPT_DIR = Path(__file__).parents[1] / "generation/prompts"
ANSWER_PROMPT = (PROMPT_DIR / "answer.md").read_text(encoding="utf-8")
QUERY_PLAN_PROMPT = (PROMPT_DIR / "query_plan.md").read_text(encoding="utf-8")


class LLMGateway:
    def __init__(self, settings):
        self.settings = settings

    def generate(self, query, evidence, request_id=None):
        content, diagnostics = self._request_completion(
            ANSWER_PROMPT,
            {"question": query, "evidence": evidence},
            request_id=request_id,
            max_tokens=self.settings.llm_max_tokens,
            input_context={
                "question_chars": len(query),
                "evidence_count": len(evidence),
                "evidence_chars": sum(
                    len(item.get("text", "")) for item in evidence if isinstance(item, dict)
                ),
            },
        )
        decoded = self._decode_json(content, request_id, diagnostics)
        try:
            return GeneratedAnswer.model_validate(decoded)
        except ValidationError as exc:
            self._response_error(
                request_id, "LLM_SCHEMA_INVALID",
                "模型返回了 JSON，但字段不符合回答协议",
                category="schema_invalid", **diagnostics,
            )
            raise AssertionError("unreachable") from exc

    def plan_query(self, query, history=None, context=None, request_id=None):
        content, diagnostics = self._request_completion(
            QUERY_PLAN_PROMPT,
            {
                "query": query,
                "history": history or [],
                "context": context or {},
            },
            request_id=request_id,
            max_tokens=min(self.settings.llm_max_tokens, 512),
            timeout_seconds=min(
                self.settings.llm_timeout_seconds,
                self.settings.query_planner_timeout_seconds,
            ),
            input_context={
                "question_chars": len(query),
                "history_turns": len(history or []),
            },
        )
        decoded = self._decode_json(content, request_id, diagnostics)
        try:
            return QueryPlan.model_validate(decoded)
        except ValidationError as exc:
            self._response_error(
                request_id, "LLM_QUERY_PLAN_INVALID",
                "模型返回的检索计划不符合约定格式",
                category="query_plan_invalid", **diagnostics,
            )
            raise AssertionError("unreachable") from exc

    def _request_completion(
        self, system_prompt, user_payload, request_id, max_tokens, input_context,
        timeout_seconds=None,
    ):
        if not self.settings.llm_base_url or not self.settings.llm_model:
            raise AppError("LLM_NOT_CONFIGURED", "请配置 LLM_BASE_URL 和 LLM_MODEL", 503)

        try:
            response = httpx.post(
                self.settings.llm_base_url.rstrip("/") + "/chat/completions",
                headers={"Authorization": "Bearer " + self.settings.llm_api_key.get_secret_value()},
                json={
                    "model": self.settings.llm_model, "temperature": 0,
                    "max_tokens": max_tokens,
                    "response_format": {"type": "json_object"},
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)},
                    ],
                },
                timeout=timeout_seconds or self.settings.llm_timeout_seconds,
            )
        except httpx.TimeoutException as exc:
            logger.warning("llm_request_failed request_id=%s category=timeout", request_id or "-")
            raise AppError("LLM_TIMEOUT", "模型服务响应超时，请稍后重试", 504) from exc
        except httpx.InvalidURL as exc:
            logger.warning("llm_request_failed request_id=%s category=invalid_url", request_id or "-")
            raise AppError("LLM_CONFIG_INVALID", "模型服务地址配置无效", 503) from exc
        except httpx.RequestError as exc:
            logger.warning("llm_request_failed request_id=%s category=network", request_id or "-")
            raise AppError("LLM_UNAVAILABLE", "无法连接模型服务，请检查服务状态或网络", 503) from exc

        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code
            logger.warning(
                "llm_request_failed request_id=%s category=http_status status=%s",
                request_id or "-", status,
            )
            if status in (401, 403):
                raise AppError(
                    "LLM_AUTH_FAILED", "模型服务认证失败，请检查 LLM_API_KEY", 502,
                ) from exc
            if status == 429:
                raise AppError(
                    "LLM_RATE_LIMITED", "模型服务当前限流，请稍后重试", 503,
                ) from exc
            if status == 408:
                raise AppError("LLM_TIMEOUT", "模型服务响应超时，请稍后重试", 504) from exc
            if status >= 500:
                raise AppError(
                    "LLM_UNAVAILABLE", "模型服务暂时不可用，请稍后重试", 503,
                ) from exc
            raise AppError(
                "LLM_REQUEST_REJECTED", "模型服务拒绝了请求，请检查模型名称和接口参数", 502,
            ) from exc

        try:
            payload = response.json()
        except ValueError as exc:
            self._response_error(
                request_id, "LLM_PROVIDER_RESPONSE_INVALID",
                "模型服务返回的响应不是有效 JSON", category="invalid_envelope",
                status=response.status_code, **input_context,
            )
            raise AssertionError("unreachable") from exc

        if not isinstance(payload, dict):
            self._response_error(
                request_id, "LLM_PROVIDER_RESPONSE_INVALID",
                "模型服务响应结构无效", category="invalid_envelope",
                status=response.status_code, **input_context,
            )

        choices = payload.get("choices")
        if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
            self._response_error(
                request_id, "LLM_PROVIDER_RESPONSE_INVALID",
                "模型服务响应缺少 choices 结果", category="missing_choices",
                status=response.status_code, **input_context,
            )

        choice = choices[0]
        finish_reason = choice.get("finish_reason")
        usage = payload.get("usage")
        completion_tokens = usage.get("completion_tokens") if isinstance(usage, dict) else None
        message = choice.get("message")
        if not isinstance(message, dict):
            self._response_error(
                request_id, "LLM_PROVIDER_RESPONSE_INVALID",
                "模型服务响应缺少 message 内容", category="missing_message",
                status=response.status_code, finish_reason=finish_reason or "unknown",
                **input_context,
            )
        content = message.get("content")
        content_length = len(content) if isinstance(content, str) else 0
        diagnostics = {
            "finish_reason": finish_reason or "unknown",
            "completion_tokens": completion_tokens if completion_tokens is not None else "unknown",
            "content_length": content_length,
            "status": response.status_code,
            **input_context,
        }

        if finish_reason == "length":
            self._response_error(
                request_id, "LLM_OUTPUT_TRUNCATED",
                "模型输出达到 token 上限而被截断；请缩短问题或证据，或调高 LLM_MAX_TOKENS 后重试",
                category="truncated", **diagnostics,
            )
        if finish_reason == "content_filter":
            self._response_error(
                request_id, "LLM_OUTPUT_BLOCKED",
                "模型服务的内容安全策略阻止了本次回答",
                category="content_filter", **diagnostics,
            )
        if not isinstance(content, str) or not content.strip():
            self._response_error(
                request_id, "LLM_EMPTY_RESPONSE",
                "模型服务返回了空内容；请重试，若持续发生请检查模型服务记录",
                category="empty_content", **diagnostics,
            )
        return content, diagnostics

    def _decode_json(self, content, request_id, diagnostics):
        try:
            return json.loads(content)
        except json.JSONDecodeError as exc:
            self._response_error(
                request_id, "LLM_INVALID_JSON",
                "模型输出不是完整 JSON；可能被截断或未遵循 JSON 输出约束",
                category="invalid_json", **diagnostics,
            )
            raise AssertionError("unreachable") from exc

    @staticmethod
    def _response_error(request_id, code, message, category, **details) -> NoReturn:
        safe_details = " ".join(f"{key}={value}" for key, value in details.items())
        logger.warning(
            "llm_response_failed request_id=%s category=%s %s",
            request_id or "-", category, safe_details,
        )
        raise AppError(code, message, 502)
