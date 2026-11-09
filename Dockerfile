FROM node:24-alpine AS frontend
WORKDIR /build
COPY web/package.json web/package-lock.json ./
RUN npm ci
COPY web/ ./
RUN npm run typecheck && npm run test && npm run build

FROM python:3.13-slim
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 HISABGUARD_DATA_DIR=/var/lib/hisabguard
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt \
    && useradd --uid 10001 --create-home operator \
    && mkdir -p /var/lib/hisabguard \
    && chown operator:operator /var/lib/hisabguard
COPY app/ ./app/
COPY --from=frontend /build/dist ./web/dist
USER operator
VOLUME ["/var/lib/hisabguard"]
EXPOSE 8834
HEALTHCHECK --interval=30s --timeout=5s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8834/api/status', timeout=3)"
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8834"]
