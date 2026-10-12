import pytest

from app.core.exceptions import AppError
from app.ingestion.chunking import split_document
from app.ingestion.cleaning import clean_text
from app.ingestion.parsers.markdown import MarkdownParser
from app.retrieval.filters import build_filter
from app.retrieval.fusion import reciprocal_rank_fusion
from app.schemas.parsed_document import ParsedBlock, ParsedDocument
from app.schemas.query_context import QueryContext
from app.security.upload_validation import validate_upload
from tests.fakes import CharacterTokenizer


def test_markdown_preserves_code_and_positions():
    body = "# Setup\n\n" + chr(96) * 3 + "yaml\n  DB_HOST: mysql-8.0\n# comment\n" + chr(96) * 3
    parsed = MarkdownParser().parse(body.encode())
    assert any("  DB_HOST: mysql-8.0" in b.text for b in parsed.blocks)
    assert all(b.title_path == "Setup" for b in parsed.blocks)
    assert parsed.blocks[-1].anchor == "L3"


def test_cleaning_preserves_identifiers():
    assert clean_text("  GB/T-1.2\r\nDEMO_DB-001") == "  GB/T-1.2\nDEMO_DB-001"


def test_chunks_cover_original_with_bounded_overlap():
    original = "abcdefghijklmnopqrstuvwxyz"
    parsed = ParsedDocument(blocks=[ParsedBlock(text=original, page=7, anchor="p7")])
    chunks = split_document(parsed, CharacterTokenizer(), 10, 2)
    assert chunks[0].text + "".join(c.text[2:] for c in chunks[1:]) == original
    assert all(c.token_count <= 10 and c.page == 7 for c in chunks)
    assert all(c.text in original for c in chunks)


def test_rrf_reference_order_and_duplicate_protection():
    result = reciprocal_rank_fusion([["A", "B", "C"], ["C", "A", "D"]])
    assert [identifier for identifier, _ in result] == ["A", "C", "B", "D"]
    assert reciprocal_rank_fusion([["A", "A"]])[0][1] == pytest.approx(1 / 61)


def test_filter_escapes_untrusted_values_and_applies_both_security_scopes():
    value = 'x" or tenant_id != ""'
    expr = build_filter("tenant-a", ["kb-a"], QueryContext(product_version=value), "v1")
    assert 'tenant_id == "tenant-a"' in expr
    assert 'knowledge_base_id in ["kb-a"]' in expr
    assert r'x\" or tenant_id != \"\"' in expr
    assert 'publication_status == "PUBLISHED"' in expr


@pytest.mark.parametrize("name,data,code", [
    ("virus.exe", b"anything", "UNSUPPORTED_TYPE"),
    ("fake.pdf", b"not a pdf", "INVALID_PDF"),
    ("fake.docx", b"not a zip", "INVALID_DOCX"),
    ("empty.md", b"", "EMPTY_FILE"),
    ("binary.md", b"\x00abcd", "INVALID_TEXT"),
])
def test_upload_rejects_invalid_inputs(name, data, code):
    with pytest.raises(AppError) as error:
        validate_upload(name, data, 1024)
    assert error.value.code == code

