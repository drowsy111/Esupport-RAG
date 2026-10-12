import json


def literal(value) -> str:
    return json.dumps(value, ensure_ascii=False)


def build_filter(tenant_id, knowledge_base_ids, context, embedding_version):
    clauses = [
        f"tenant_id == {literal(tenant_id)}",
        f"knowledge_base_id in {literal(list(knowledge_base_ids))}",
        "is_active == true",
        'publication_status == "PUBLISHED"',
        f"embedding_version == {literal(embedding_version)}",
    ]
    for field in ("product_id", "product_version", "deployment_mode"):
        value = getattr(context, field, None)
        if value:
            clauses.append(f'({field} == {literal(value)} or {field} == "")')
    return " and ".join(clauses)

