import pytest

from app.ingestion.sentence_chunking import split_sentences
from app.retrieval.context_builder import build_context
from app.retrieval.sentence_window import make_windows, window_cost
from app.schemas.parsed_document import ParsedBlock, ParsedDocument
from app.schemas.retrieval import Candidate
from tests.fakes import CharacterTokenizer


def test_sentences_preserve_source_and_technical_identifiers():
    text = "使用 v2.4.1。Check https://host.local/a. Ask Dr. Li. Then restart!"
    chunks = split_sentences(ParsedDocument(blocks=[ParsedBlock(text=text)]),
                            CharacterTokenizer(), 200)
    assert "".join(c.text for c in chunks) == text
    assert [c.text.strip() for c in chunks] == [
        "使用 v2.4.1。", "Check https://host.local/a.", "Ask Dr. Li.", "Then restart!",
    ]
    assert all(c.text == text[c.structure["start"]:c.structure["end"]] for c in chunks)


def test_long_sentence_partitions_without_overlap_or_data_loss():
    text = "abcdef " * 30
    chunks = split_sentences(ParsedDocument(blocks=[ParsedBlock(text=text)]),
                            CharacterTokenizer(), 32)
    assert "".join(c.text for c in chunks) == text
    assert all(c.token_count <= 32 for c in chunks)


def test_code_list_and_table_are_not_split_at_sentence_punctuation():
    text = "```sh\necho 'a。b。'\n```\n- 检查。然后重试。\n| A。 | B。 |\n"
    chunks = split_sentences(ParsedDocument(blocks=[ParsedBlock(text=text)]),
                            CharacterTokenizer(), 200)
    assert len(chunks) == 3
    assert chunks[0].text.startswith("```sh") and chunks[0].text.endswith("```\n")
    assert "".join(c.text for c in chunks) == text


def candidate(index, section=0, version="v", text=None):
    text = text or f"Sentence {index}."
    return Candidate(
        chunk_id=f"{version}-{index}", document_id="doc", version_id=version,
        document_name="guide", revision=1, text=text, content_hash=f"hash-{index}",
        title_path="Setup", chunk_index=index, token_count=10,
        structure={"strategy": "sentence-v1", "section": section, "block": index,
                   "start": 0, "end": len(text)},
        matched_text=text, matched_chunk_ids=[f"{version}-{index}"],
    )


def test_overlapping_windows_merge_in_document_order_and_keep_matches():
    units = [candidate(i) for i in range(7)]
    windows = make_windows([units[2], units[3]], units, 2, 80)
    assert len(windows) == 1
    assert [s.chunk_index for s in windows[0].sources] == list(range(6))
    assert set(windows[0].matched_chunk_ids) == {"v-2", "v-3"}
    assert window_cost(windows[0].sources) <= 80


@pytest.mark.parametrize("boundary", ["section", "version", "missing"])
def test_window_stops_at_boundary_or_missing_authorized_neighbor(boundary):
    units = [candidate(i) for i in range(5)]
    if boundary == "section":
        units[3] = candidate(3, section=1)
    elif boundary == "version":
        units[3] = candidate(3, version="other")
    else:
        units.pop(3)
    window = make_windows([units[2]], units, 2, 100)[0]
    assert [s.chunk_index for s in window.sources] == [0, 1, 2]


def test_merging_never_exceeds_budget_or_drops_core():
    units = [candidate(i) for i in range(8)]
    windows = make_windows([units[2], units[4]], units, 2, 34)
    assert len(windows) == 2
    assert all(window_cost(w.sources) <= 34 for w in windows)
    assert {"v-2", "v-4"} <= {s.chunk_id for w in windows for s in w.sources}


def test_legacy_chunks_remain_unexpanded():
    core = candidate(2).model_copy(update={"structure": None})
    window = make_windows([core], [candidate(i) for i in range(5)], 2, 100)[0]
    assert window.text == core.text
    assert len(window.sources) == 1


def test_repeated_heading_and_pdf_page_create_distinct_sections():
    blocks = [ParsedBlock(text="Same", title_path="Same", starts_section=True),
              ParsedBlock(text="Body", title_path="Same"),
              ParsedBlock(text="Same", title_path="Same", starts_section=True),
              ParsedBlock(text="Page", page=1), ParsedBlock(text="Page", page=2)]
    chunks = split_sentences(ParsedDocument(blocks=blocks), CharacterTokenizer(), 200)
    assert [c.structure["section"] for c in chunks] == [0, 0, 1, 2, 3]


def test_context_budget_accounts_for_serialized_metadata_and_escaping():
    import json

    units = [candidate(1, text='"' * 1000), candidate(2, text="short")]
    evidence, mapping = build_context(units, 500)
    assert len(evidence) == 1
    assert mapping["c1"].chunk_id == "v-2"
    assert len(json.dumps(evidence, ensure_ascii=False)) <= 500
