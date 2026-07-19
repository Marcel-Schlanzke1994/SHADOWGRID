FROM python:3.13-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/apps/api

RUN addgroup --system shadowgrid && adduser --system --ingroup shadowgrid shadowgrid
WORKDIR /app
COPY apps/api/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir --requirement /tmp/requirements.txt
COPY apps/api /app/apps/api
COPY apps/worker /app/apps/worker
RUN chown -R shadowgrid:shadowgrid /app
USER shadowgrid
WORKDIR /app/apps/api

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import os,urllib.request; urllib.request.urlopen('http://127.0.0.1:'+os.getenv('PORT','8000')+'/api/v1/health', timeout=3)"

CMD ["sh", "-c", "exec python -m uvicorn shadowgrid.main:app --host 0.0.0.0 --port \"${PORT:-8000}\" --proxy-headers"]
