# Stateless Google ADK + FastAPI backend (zero database; single container free-tier ready).
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PORT=8000 GOOGLE_GENAI_USE_VERTEXAI=FALSE
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
COPY stylist_agent ./stylist_agent
RUN useradd --create-home shopper && mkdir -p /app/data/profiles && chown -R shopper /app
USER shopper
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s CMD python -c "import os,urllib.request; urllib.request.urlopen(f'http://127.0.0.1:{os.environ.get(\"PORT\",\"8000\")}/health')" || exit 1
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
