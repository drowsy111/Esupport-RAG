"""Source-preserving sentence units; oversized units use nonoverlapping token windows."""
import re

from app.core.exceptions import AppError
from app.ingestion.cleaning import clean_text
from app.schemas.chunk import ChunkDraft


def semantic_spans(text):
    # Treat fenced code, tables and list items as atomic lines/blocks. Never split
    # on a decimal point, URL dot, or an English abbreviation followed by text.
    cursor = 0
    fence = None
    fence_start = 0
    for line in text.splitlines(keepends=True):
        marker = re.match(r"^\s*(`{3,}|~{3,})", line)
        if fence:
            if marker and marker[1][0] == fence[0] and len(marker[1]) >= len(fence):
                yield fence_start, cursor + len(line)
                fence = None
        elif marker:
            fence, fence_start = marker[1], cursor
        elif re.match(r"^\s*(?:#{1,6}\s|[-*+]\s|\d+[.)]\s|\|)", line) or " | " in line:
            yield cursor, cursor + len(line)
        else:
            start = 0
            for boundary in re.finditer(r"[。！？!?]+[\"'”’）)]*\s*|\.(?=\s|$)\s*", line):
                if boundary[0].startswith("."):
                    prefix = line[:boundary.start()]
                    word = re.search(r"([\w.]+)$", prefix)
                    # Keep common abbreviations and initials together.
                    if word and (word[1].lower() in {
                        "mr", "mrs", "ms", "dr", "prof", "e.g", "i.e", "vs", "etc",
                    } or (len(word[1]) == 1 and word[1].isupper())):
                        continue
                yield cursor + start, cursor + boundary.end()
                start = boundary.end()
            if start < len(line):
                yield cursor + start, cursor + len(line)
        cursor += len(line)
    if fence:
        yield fence_start, len(text)


def split_sentences(parsed, tokenizer, max_tokens):
    chunks = []
    section = -1
    previous = None
    for block_index, block in enumerate(parsed.blocks):
        text = clean_text(block.text)
        # PDF has no reliable heading extraction: keep windows on one page.
        boundary = (block.title_path, block.page)
        if boundary != previous or block.starts_section:
            section += 1
        previous = boundary
        for begin, finish in semantic_spans(text):
            unit = text[begin:finish]
            if not unit.strip():
                continue
            offsets = tokenizer(unit, add_special_tokens=False, return_offsets_mapping=True)[
                "offset_mapping"
            ]
            for start in range(0, len(offsets), max_tokens):
                end = min(start + max_tokens, len(offsets))
                # Partition source spans without dropping whitespace between token offsets.
                left = 0 if start == 0 else offsets[start][0]
                right = len(unit) if end == len(offsets) else offsets[end][0]
                piece = unit[left:right]
                if not piece.strip():
                    continue
                chunks.append(ChunkDraft(
                    text=piece, title_path=block.title_path, page=block.page,
                    anchor=block.anchor, token_count=end - start,
                    structure={"strategy": "sentence-v1", "section": section,
                               "block": block_index, "start": begin + left,
                               "end": begin + right},
                ))
                if len(chunks) > 10000:
                    raise AppError("TOO_MANY_CHUNKS", "单文档超过 Chunk 数量限制")
    if not chunks:
        raise AppError("EMPTY_DOCUMENT", "清洗后没有可索引内容")
    return chunks
