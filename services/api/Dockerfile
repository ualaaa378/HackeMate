FROM python:3.13-slim
WORKDIR /srv
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY alembic.ini .
COPY migraciones ./migraciones
COPY app ./app
EXPOSE 8000
HEALTHCHECK CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"
# Crea o actualiza las tablas y carga los datos de la demo antes de arrancar (db ya está "healthy" por el
# depends_on del compose). El seed es repetible: solo toca los datos de contracts/fixtures.
CMD ["sh", "-c", "python -m app.seed && exec uvicorn app.main:app --host 0.0.0.0 --port 8000"]
