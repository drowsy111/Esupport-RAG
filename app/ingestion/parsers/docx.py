import io

from docx import Document
from docx.table import Table
from docx.text.paragraph import Paragraph

from app.core.exceptions import AppError
from app.schemas.parsed_document import ParsedBlock, ParsedDocument


class DOCXParser:
    """解析 Word 文档中的段落和结构。"""

    def parse(self, data: bytes) -> ParsedDocument:
        try:
            doc = Document(io.BytesIO(data))
            blocks, headings = [], []
            for number, item in enumerate(doc.iter_inner_content(), 1):
                starts_section = False
                if isinstance(item, Paragraph):
                    text = item.text
                    style = item.style.name if item.style else ""
                    if style.startswith("Heading ") and style[-1:].isdigit():
                        starts_section = True
                        level = int(style[-1])
                        headings = headings[:level - 1] + [text]
                elif isinstance(item, Table):
                    text = "\n".join(
                        " | ".join(cell.text.replace("\n", " / ") for cell in row.cells)
                        for row in item.rows
                    )
                else:
                    continue
                if text.strip():
                    blocks.append(ParsedBlock(
                        text=text, title_path=" > ".join(headings)[-1000:],
                        anchor=f"block-{number}",
                        starts_section=starts_section,
                    ))
            return ParsedDocument(
                blocks=blocks, warnings=["DOCX 引用使用正文块位置，不推算页码"],
            )
        except Exception as exc:
            raise AppError("PARSE_FAILED", "DOCX 无法解析") from exc

