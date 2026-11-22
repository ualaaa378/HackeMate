# 3.12 y no 3.13: con python:3.13-slim (3.13.18) el proceso muere con «Segmentation fault» (exit 139) cuando
# llegan unas 12 peticiones a la vez, como hace la web al abrir la agenda. Reproducido en Docker el sáb 21/11;
# con 3.12 aguanta 1800 peticiones en paralelo y pasan los 592 tests.
FROM python:3.12-slim
WORKDIR /srv
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY alembic.ini .
COPY migraciones ./migraciones
COPY app ./app
EXPOSE 8000
HEALTHCHECK CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"
# Crea o actualiza las tablas y añade los datos de la demo que falten antes de arrancar (db ya está "healthy" por
# el depends_on del compose). --solo-nuevos: un reinicio NO devuelve los datos de la demo a los fixtures, así que lo
# que hagan las personas (inscripciones, cambios de hora, decisiones del moderador) se queda guardado.
# Detrás del nginx de la web y del túnel: --proxy-headers hace caso a X-Forwarded-Proto/For para que la API vea
# https y la IP real (y las redirecciones que genere salgan con https y el dominio público).
CMD ["sh", "-c", "python -m app.seed --solo-nuevos && exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --proxy-headers --forwarded-allow-ips='*'"]
