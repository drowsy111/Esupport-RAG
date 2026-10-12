from app.core.exceptions import AppError
from app.schemas.chat import Citation


def validate_and_render(result, mapping):
    if result.status != "answered":
        return result.message or "现有资料不足，请补充版本、环境或错误信息。", []
    if not result.claims:
        raise AppError("INVALID_CITATION", "回答缺少可核对的证据", 502)
    cited, lines = [], []
    for claim in result.claims:
        for identifier in claim.citation_ids:
            if identifier not in mapping:
                raise AppError("INVALID_CITATION", "模型引用了不存在的证据", 502)
            if identifier not in cited:
                cited.append(identifier)
        markers = " ".join(f"[{x}]" for x in claim.citation_ids)
        lines.append(f"{claim.text} {markers}")
    citations = []
    for identifier in cited:
        candidate = mapping[identifier]
        citations.append(Citation(
            citation_id=identifier, document_id=candidate.document_id,
            document_name=candidate.document_name, revision=candidate.revision,
            chunk_id=candidate.chunk_id, page=candidate.page, anchor=candidate.anchor,
            # Server-owned excerpt, never the model's alleged quote.
            quote=candidate.text, source_kind=candidate.source_kind,
            matched_text=candidate.matched_text, matched_chunk_ids=candidate.matched_chunk_ids,
            sources=candidate.sources,
        ))
    return "\n\n".join(lines), citations

