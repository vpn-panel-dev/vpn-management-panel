FROM python:3.14-slim
WORKDIR /app

COPY pyproject.toml .
RUN pip install --no-cache-dir uv && uv pip install --system -r pyproject.toml

COPY app/ ./app/

CMD ["python", "-m", "app.main"]
