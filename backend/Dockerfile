FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /srv
COPY pyproject.toml ./
COPY app ./app
RUN pip install . && useradd --create-home appuser
USER appuser

ENV PORT=8000
EXPOSE 8000
# Hosts like Render/Fly/Railway inject $PORT.
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT} --no-access-log"]
