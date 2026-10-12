import json


def build_context(candidates, char_budget):
    evidence, mapping, used = [], {}, 0
    for candidate in candidates:
        identifier = f"c{len(evidence) + 1}"
        item = {
            "id": identifier, "document": candidate.document_name,
            "section": candidate.title_path, "product_version": candidate.product_version,
            "source_kind": candidate.source_kind, "text": candidate.text,
        }
        cost = len(json.dumps(item, ensure_ascii=False)) + 2
        if used + cost > char_budget:
            continue
        evidence.append(item)
        mapping[identifier] = candidate
        used += cost
    return evidence, mapping

