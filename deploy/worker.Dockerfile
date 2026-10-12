FROM python:3.12-slim
WORKDIR /srv/rag
COPY pyproject.toml ./
COPY app ./app
RUN pip install --no-cache-dir .
RUN useradd --uid 10001 --create-home rag && chown -R rag:rag /srv/rag
USER rag
CMD ["celery", "-A", "app.workers.celery_app:celery_app", "worker", "-Q", "ingestion", "--concurrency=1", "--loglevel=INFO"]

