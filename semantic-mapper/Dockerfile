FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml ./
COPY src/ ./src/
COPY resources/ ./resources/

RUN pip install --no-cache-dir .

ENV SEMANTIC_MAPPER_RESOURCES_DIR=/app/resources
ENV SEMANTIC_MAPPER_STATE_DIR=/semantic-mapper/state

EXPOSE 8000

CMD ["uvicorn", "semantic_mapper.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
