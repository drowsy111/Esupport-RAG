import json
from pathlib import Path

import httpx

from app.core.exceptions import AppError
from app.schemas.chat import GeneratedAnswer

PROMPT = (Path(__file__).parents[1] / "generation/prompts/answer.md").read_text(encoding="utf-8")


class LLMGateway:
    def __init__(self, settings):
        self.settings = settings

    def generate(self, query, evidence):
        if not self.settings.llm_base_url or not self.settings.llm_model:
            raise AppError("LLM_NOT_CONFIGURED", "请配置 LLM_BASE_URL 和 LLM_MODEL", 503)
        # Common chat-completions protocol. Provider must support JSON response mode.
        try:
            response = httpx.post(
                self.settings.llm_base_url.rstrip("/") + "/chat/completions",
                headers={"Authorization": "Bearer " + self.settings.llm_api_key.get_secret_value()},
                json={
                    "model": self.settings.llm_model, "temperature": 0, "max_tokens": 1800,
                    "response_format": {"type": "json_object"},
                    "messages": [
                        {"role": "system", "content": PROMPT},
                        {"role": "user", "content": json.dumps({
                            "question": query, "evidence": evidence,
                        }, ensure_ascii=False)},
                    ],
                },
                timeout=self.settings.llm_timeout_seconds,
            )
            response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"]
            return GeneratedAnswer.model_validate_json(content)
        except Exception as exc:
            raise AppError("LLM_RESPONSE_INVALID", "模型调用失败或返回格式不符合约定", 502) from exc

