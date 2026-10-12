import io

from pypdf import PdfReader

from app.core.exceptions import AppError
from app.schemas.parsed_document import ParsedBlock, ParsedDocument


class PDFParser:
    """
    解析 PDF 内容和页面信息。
    """
    def parse(self, data: bytes) -> ParsedDocument:
        try:
            reader = PdfReader(io.BytesIO(data))
            if reader.is_encrypted:
                raise AppError("ENCRYPTED_PDF", "第一阶段不支持加密 PDF")
            if len(reader.pages) > 300:
                raise AppError("TOO_MANY_PAGES", "PDF 超过 300 页限制")
            blocks = []
            for number, page in enumerate(reader.pages, 1):
                text = page.extract_text() or ""
                if not text.strip():
                    raise AppError("OCR_REQUIRED", f"PDF 第 {number} 页无文本层，需要 OCR")
                blocks.append(ParsedBlock(text=text, page=number, anchor=f"page-{number}"))
            return ParsedDocument(blocks=blocks)
        except AppError:
            raise
        except Exception as exc:
            raise AppError("PARSE_FAILED", "PDF 无法解析") from exc

