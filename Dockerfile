# One container for hosting: builds the website, then serves it and the API (under /api) with FastAPI.
FROM node:22-slim AS web
WORKDIR /src
COPY web/package.json web/package-lock.json ./web/
RUN npm ci --prefix web
COPY assets ./assets
COPY web ./web
RUN npm run build --prefix web

FROM python:3.13-slim
WORKDIR /app
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/app ./app
COPY --from=web /src/web/dist ./web
# The SQLite database lives on a volume mounted at /data so it survives redeploys.
RUN mkdir -p /data
ENV WEB_DIST=/app/web \
    DATABASE_URL=sqlite:////data/sdu_campus.db \
    COOKIE_SECURE=true
EXPOSE 8000
CMD ["sh", "-c", "uvicorn app.server:site --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips='*'"]
