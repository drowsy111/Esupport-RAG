"""Expand authorized hits locally, merge overlapping windows within a bounded budget."""


def compatible(core, other):
    return (
        core.structure and other.structure
        and core.structure.get("strategy") == other.structure.get("strategy") == "sentence-v1"
        and (core.document_id, core.version_id, core.structure["section"], core.title_path)
        == (other.document_id, other.version_id, other.structure["section"], other.title_path)
    )


def window_cost(sources):
    # Persisted BGE token counts plus conservative separators; no tokenizer download
    # in the API process. This is not the target LLM's exact token count.
    return sum(s.token_count for s in sources) + 2 * max(0, len(sources) - 1)


def join_sources(sources):
    result = ""
    previous = None
    for source in sources:
        contiguous = (
            previous and previous.structure and source.structure
            and previous.structure["block"] == source.structure["block"]
            and previous.structure["end"] == source.structure["start"]
        )
        result += ("" if not result or contiguous else "\n\n") + source.text
        previous = source
    return result


def make_windows(candidates, neighbors, radius, max_tokens):
    lookup = {(c.version_id, c.chunk_index): c for c in neighbors}
    windows = []
    for core in candidates:
        members = {core.chunk_index: core.as_source()}
        blocked = set()
        for distance in range(1, radius + 1):
            for direction in (-1, 1):
                if direction in blocked:
                    continue
                neighbor = lookup.get((core.version_id, core.chunk_index + direction * distance))
                if not neighbor or not compatible(core, neighbor):
                    blocked.add(direction)
                    continue
                proposed = [*members.values(), neighbor.as_source()]
                if window_cost(proposed) > max_tokens:
                    blocked.add(direction)
                    continue
                members[neighbor.chunk_index] = neighbor.as_source()
        sources = [members[i] for i in sorted(members)]
        window = core.model_copy(update={"sources": sources, "text": join_sources(sources)})
        windows.append(window)

    # Merge only when the union fits; never truncate away a retrieved core sentence.
    merged = []
    for window in windows:
        index = 0
        while index < len(merged):
            other = merged[index]
            ids = {s.chunk_id for s in window.sources}
            if (compatible(window, other)
                    and ids.intersection(s.chunk_id for s in other.sources)):
                union = {s.chunk_id: s for s in [*window.sources, *other.sources]}
                sources = sorted(union.values(), key=lambda s: s.chunk_index)
                if window_cost(sources) <= max_tokens:
                    core = max((window, other), key=lambda c: c.fusion_score)
                    window = core.model_copy(update={
                        "text": join_sources(sources), "sources": sources,
                        "matched_chunk_ids": list(dict.fromkeys(
                            other.matched_chunk_ids + window.matched_chunk_ids)),
                    })
                    merged.pop(index)
                    index = 0
                    continue
            index += 1
        merged.append(window)
    return sorted(merged, key=lambda c: c.fusion_score, reverse=True)
