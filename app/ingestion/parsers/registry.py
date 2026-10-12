from app.core.exceptions import AppError

def parse_document(file_type: str, data: bytes):
    if file_type == "pdf":
        from .pdf import PDFParser
        parser = PDFParser()
    elif file_type == "docx":
        from .docx import DOCXParser
        parser = DOCXParser()
    elif file_type == "md":
        from .markdown import MarkdownParser
        parser = MarkdownParser()
    else:
        raise AppError("UNSUPPORTED_TYPE", "解析器不支持此格式")
    # return ParsedDocument->blocks: list[ParsedBlock]
    result = parser.parse(data)   
    if not result.blocks:
        raise AppError("EMPTY_DOCUMENT", "未能提取正文")
    return result
