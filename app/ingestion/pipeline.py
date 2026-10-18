from app.ingestion.parsers.registry import parse_document
from app.ingestion.sentence_chunking import split_sentences


def parse_and_chunk(data, file_type, tokenizer, settings):
    """解析、清洗和切分原文件，返回解析结果和 ChunkDraft 列表供向量化使用。"""
    parsed = parse_document(file_type, data)
    chunks = split_sentences(
        parsed, tokenizer, settings.sentence_max_tokens, settings.sentence_min_tokens,
    )
    return parsed, chunks
