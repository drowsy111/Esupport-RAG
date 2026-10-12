from app.core.config import get_settings
from app.integrations.milvus_client import VectorStore
from app.integrations.object_storage import ObjectStorage


def main():
    settings = get_settings()
    settings.validate_runtime()
    storage = ObjectStorage(settings)
    storage.ensure_bucket()
    vector_store = VectorStore(settings)
    try:
        vector_store.initialize()
    finally:
        vector_store.close()
    print("Bucket and Milvus collection initialized; existing data was not deleted.")


if __name__ == "__main__":
    main()

