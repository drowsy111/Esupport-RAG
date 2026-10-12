import io
import zipfile
from pathlib import PurePosixPath

from app.core.exceptions import AppError


def validate_upload(filename: str, data: bytes, max_bytes: int) -> tuple[str, str]:
    name = PurePosixPath((filename or "").replace("\\", "/")).name
    if not name or len(name) > 240:
        raise AppError("INVALID_FILENAME", "文件名无效")
    suffix = PurePosixPath(name).suffix.lower()
    if suffix not in {".pdf", ".docx", ".md"}:
        raise AppError("UNSUPPORTED_TYPE", "仅支持 PDF、DOCX 和 Markdown", 415)
    if not data:
        raise AppError("EMPTY_FILE", "文件内容为空")
    if len(data) > max_bytes:
        raise AppError("FILE_TOO_LARGE", "文件超过大小限制", 413)
    if suffix == ".pdf" and not data.startswith(b"%PDF-"):
        raise AppError("INVALID_PDF", "文件内容不是 PDF")
    if suffix == ".docx":
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as archive:
                infos = archive.infolist()
                if len(infos) > 5000 or sum(i.file_size for i in infos) > 50 * 1024 * 1024:
                    raise AppError("ARCHIVE_TOO_LARGE", "DOCX 解压内容超过限制")
                if "word/document.xml" not in archive.namelist():
                    raise AppError("INVALID_DOCX", "DOCX 缺少正文")
        except (zipfile.BadZipFile, RuntimeError) as exc:
            raise AppError("INVALID_DOCX", "无效的 DOCX") from exc
    if suffix == ".md":
        try:
            text = data.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise AppError("INVALID_ENCODING", "Markdown 必须使用 UTF-8") from exc
        if "\x00" in text:
            raise AppError("INVALID_TEXT", "Markdown 包含二进制内容")
    return name, suffix.lstrip(".")

