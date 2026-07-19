FROM node:22.16-alpine AS web-build
RUN corepack enable && corepack prepare pnpm@11.1.3 --activate
WORKDIR /app
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
COPY packages ./packages
COPY apps/web ./apps/web
RUN pnpm install --frozen-lockfile
RUN pnpm --filter @shadowgrid/web build

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
COPY --from=web-build /app/apps/web/dist /app/apps/api/web-dist
RUN chown -R shadowgrid:shadowgrid /app
USER shadowgrid
WORKDIR /app/apps/api

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import os,urllib.request; urllib.request.urlopen('http://127.0.0.1:'+os.getenv('PORT','8000')+'/api/v1/health', timeout=3)"

CMD ["sh", "-c", "exec python -m uvicorn shadowgrid.main:app --host 0.0.0.0 --port \"${PORT:-8000}\" --proxy-headers"]
