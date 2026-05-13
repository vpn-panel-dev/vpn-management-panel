FROM python:3.14-slim
WORKDIR /app

COPY pyproject.toml .
RUN pip install --no-cache-dir uv && uv pip install --system -r pyproject.toml

COPY app/ ./app/
COPY migrations/ ./migrations/
COPY alembic.ini .

CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8080"]
