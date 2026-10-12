import argparse
import getpass
from pathlib import Path

import httpx


def main():
    parser = argparse.ArgumentParser(description="Upload synthetic demo documents through the API")
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--tenant", default="customer-a")
    parser.add_argument("--username", default="admin")
    parser.add_argument("--knowledge-base-id", required=True)
    parser.add_argument("--directory", default="data/synthetic")
    args = parser.parse_args()
    password = getpass.getpass("Demo account password: ")
    with httpx.Client(base_url=args.base_url, timeout=120) as client:
        response = client.post("/api/v1/auth/login", json={
            "tenant_name": args.tenant, "username": args.username, "password": password,
        })
        response.raise_for_status()
        client.headers["Authorization"] = "Bearer " + response.json()["access_token"]
        for path in sorted(Path(args.directory).rglob("*.md")):
            with path.open("rb") as source:
                response = client.post(
                    "/api/v1/documents/upload",
                    data={"knowledge_base_id": args.knowledge_base_id,
                          "product_id": "supporthub-demo", "product_version": "2.4.1",
                          "deployment_mode": "docker_compose", "source_kind": "synthetic"},
                    files={"file": (path.name, source, "text/markdown")},
                )
            response.raise_for_status()
            print(path.name, response.json())


if __name__ == "__main__":
    main()

