# Etapa 1: build de Vite. Las variables VITE_* se incrustan en el JS en este momento,
# así que VITE_API_URL tiene que ser una URL que resuelva el navegador, no el nombre del servicio.
# «/» (por defecto) = la API en el mismo dominio, a través del proxy de nginx.conf.
FROM node:26-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
ARG VITE_API_URL=/
ARG VITE_USE_MOCKS=false
ARG VITE_CANAL=telegram
ENV VITE_API_URL=$VITE_API_URL \
    VITE_USE_MOCKS=$VITE_USE_MOCKS \
    VITE_CANAL=$VITE_CANAL
RUN npm run build

# Etapa 2: nginx sirve los estáticos
FROM nginx:1.27-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 8080
