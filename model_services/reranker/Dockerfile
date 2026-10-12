FROM python:3.12-slim
WORKDIR /srv/rag
COPY pyproject.toml ./
COPY app ./app
COPY model_services ./model_services
RUN pip install --no-cache-dir ".[models]"
RUN useradd --uid 10001 --create-home rag && chown -R rag:rag /srv/rag
USER rag
CMD ["uvicorn", "model_services.reranker.main:app", "--host", "0.0.0.0", "--port", "8002", "--workers", "1"]

