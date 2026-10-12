import hashlib
import json

"""
生成文档、版本和文本块的稳定标识 64位。
"""

def content_hash(text: str | bytes) -> str:
    data = text.encode("utf-8") if isinstance(text, str) else text
    return hashlib.sha256(data).hexdigest()


def chunk_id(tenant_id: str, version_id: str, index: int, text: str) -> str:
    return content_hash(json.dumps(
        [tenant_id, version_id, "structure-token-v1", index, content_hash(text)],
        ensure_ascii=False, separators=(",", ":"),
    ))

