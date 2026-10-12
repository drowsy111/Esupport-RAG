from functools import lru_cache

from app.core.exceptions import AppError
from app.ingestion.cleaning import clean_text
from app.schemas.chunk import ChunkDraft
"""
按长度、段落或语义边界将文档切分为检索块。
"""

@lru_cache(maxsize=2)
def load_tokenizer(model: str, revision: str):
    """
    use_fast=True 开启Rust 快速分词器
    """

    from transformers import AutoTokenizer
    return AutoTokenizer.from_pretrained(model, revision=revision, use_fast=True)


def split_document(parsed, tokenizer, max_tokens: int, overlap: int) -> list[ChunkDraft]:
    """
    滑动窗口切块
    use_fast=True 开启后，tokenizer可以开启return_offsets_mapping=True 字符区间
    """
    if not 0 <= overlap < max_tokens:
        raise ValueError("invalid overlap")
    chunks = []
    for block in parsed.blocks:
        text = clean_text(block.text)
        if not text.strip():
            continue
        offsets = tokenizer(text, add_special_tokens=False, return_offsets_mapping=True)[
            "offset_mapping"
        ]
        if not offsets:
            continue

        start = 0
        while start < len(offsets):
            end = min(start + max_tokens, len(offsets))
            piece = text[offsets[start][0]:offsets[end - 1][1]]
            if piece.strip():
                chunks.append(ChunkDraft(
                    text=piece, title_path=block.title_path, page=block.page,
                    anchor=block.anchor, token_count=end - start,
                ))
            if len(chunks) > 10000:
                raise AppError("TOO_MANY_CHUNKS", "单文档超过 Chunk 数量限制")
            if end == len(offsets):
                break
            start = end - overlap
    if not chunks:
        raise AppError("EMPTY_DOCUMENT", "清洗后没有可索引内容")
    return chunks

