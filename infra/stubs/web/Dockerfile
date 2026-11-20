# Stub de la web (Flujo C) para que el compose arranque mientras apps/web no tenga Dockerfile en develop.
FROM nginx:1.27-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY index.html /usr/share/nginx/html/index.html
EXPOSE 8080
