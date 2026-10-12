def create_collection(client, name: str):
    """
    定义 Milvus 向量集合的字段、向量维度和索引参数。
    """
    from pymilvus import DataType

    if client.has_collection(name):
        info = client.describe_collection(name)
        fields = {field["name"]: field for field in info["fields"]}
        dense = fields.get("dense_vector", {})
        if int(dense.get("params", {}).get("dim", 0)) != 1024:
            raise ValueError("Existing collection has incompatible dense dimension")
        required = {
            "id", "tenant_id", "knowledge_base_id", "document_id", "version_id",
            "content_hash", "embedding_version", "publication_status", "is_active",
            "product_id", "product_version", "deployment_mode", "sparse_vector",
        }
        if not required.issubset(fields):
            raise ValueError("Existing collection has incompatible schema")
        return
    schema = client.create_schema(auto_id=False, enable_dynamic_field=False)
    schema.add_field("id", DataType.VARCHAR, is_primary=True, max_length=64)
    for name_, length in {
        "tenant_id": 36, "knowledge_base_id": 36, "document_id": 36, "version_id": 36,
        "content_hash": 64, "embedding_version": 128, "publication_status": 20,
        "product_id": 400, "product_version": 200, "deployment_mode": 200,
    }.items():
        schema.add_field(name_, DataType.VARCHAR, max_length=length)
    schema.add_field("is_active", DataType.BOOL)
    schema.add_field("dense_vector", DataType.FLOAT_VECTOR, dim=1024)
    schema.add_field("sparse_vector", DataType.SPARSE_FLOAT_VECTOR)
    indexes = client.prepare_index_params()
    indexes.add_index(
        field_name="dense_vector", index_type="HNSW", metric_type="COSINE",
        params={"M": 16, "efConstruction": 200},
    )
    indexes.add_index(
        field_name="sparse_vector", index_type="SPARSE_INVERTED_INDEX", metric_type="IP",
    )
    client.create_collection(
        collection_name=name, schema=schema, index_params=indexes, consistency_level="Strong",
    )

