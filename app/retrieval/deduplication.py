def deduplicate(candidates):
    seen, result = set(), []
    for item in candidates:
        key = (item.document_id, item.content_hash)
        if key not in seen:
            result.append(item)
            seen.add(key)
    return result

