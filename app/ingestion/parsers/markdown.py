import re

from app.schemas.parsed_document import ParsedBlock, ParsedDocument


class MarkdownParser:
    """解析 Markdown 文档并提取结构化文本。"""

    def parse(self, data: bytes) -> ParsedDocument:
        lines = data.decode("utf-8-sig").splitlines()
        blocks, headings, buffer = [], [], []
        start_line, fence = 1, None

        def flush():
            if buffer and "\n".join(buffer).strip():
                blocks.append(ParsedBlock(
                    text="\n".join(buffer), title_path=" > ".join(headings)[-1000:],
                    anchor=f"L{start_line}",
                    starts_section=bool(re.match(r"^#{1,6}\s+", buffer[0])),
                ))
            buffer.clear()

        for number, line in enumerate(lines, 1):
            stripped = line.lstrip()
            marker = re.match(r"^(\x60{3,}|~{3,})", stripped)
            if marker:
                value = marker.group(1)
                if fence is None:
                    fence = value
                elif value[0] == fence[0] and len(value) >= len(fence):
                    fence = None
            heading = re.match(r"^(#{1,6})\s+(.+)$", line) if fence is None else None
            if heading:
                flush()
                level = len(heading.group(1))
                headings = headings[:level - 1] + [heading.group(2).strip()]
                start_line = number
                buffer.append(line)
            elif not stripped and fence is None:
                flush()
                start_line = number + 1
            else:
                if not buffer:
                    start_line = number
                buffer.append(line)
        flush()
        return ParsedDocument(blocks=blocks)

