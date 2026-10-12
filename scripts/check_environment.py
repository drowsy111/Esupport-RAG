"""Read-only dependency report; no credentials, installation, or network calls."""
import importlib.metadata
import importlib.util
import sys

DEPENDENCIES = {
    "fastapi": "fastapi", "sqlalchemy": "SQLAlchemy", "pymysql": "PyMySQL",
    "pymilvus": "pymilvus", "celery": "celery", "minio": "minio",
    "jwt": "PyJWT", "multipart": "python-multipart", "alembic": "alembic",
    "pypdf": "pypdf", "docx": "python-docx", "transformers": "transformers",
    "pydantic_settings": "pydantic-settings", "pytest": "pytest", "argon2": "argon2-cffi",
    "FlagEmbedding": "FlagEmbedding", "torch": "torch",
}


def main():
    print("Python:", sys.version.split()[0])
    print("Interpreter:", sys.executable)
    missing = []
    for module, distribution in DEPENDENCIES.items():
        if importlib.util.find_spec(module) is None:
            print(distribution + ": MISSING")
            missing.append(distribution)
            continue
        try:
            version = importlib.metadata.version(distribution)
        except importlib.metadata.PackageNotFoundError:
            version = "unknown"
        print(distribution + ": " + version)
        if distribution == "pymilvus" and not version.startswith("2.4."):
            print("  Review required: project targets Milvus 2.4.4 / PyMilvus 2.4.x.")
    print("Missing packages:", len(missing))


if __name__ == "__main__":
    main()

