from typing import Protocol

from app.schemas.parsed_document import ParsedDocument


class Parser(Protocol):
    """
    Parser 协议
    """
    def parse(self, data: bytes) -> ParsedDocument: 
        ...

