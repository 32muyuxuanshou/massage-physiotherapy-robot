FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN pip install --no-cache-dir --upgrade pip

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

RUN addgroup --system appgroup \
    && adduser --system --ingroup appgroup appuser \
    && mkdir -p /app/data /app/uploads /app/logs \
    && chown -R appuser:appgroup /app

COPY --chown=appuser:appgroup app/ ./app/

USER appuser

EXPOSE 8000

CMD ["sh", "-c", "python -m app.scripts.init_db && exec uvicorn app.main:app --host 0.0.0.0 --port 8000"]
