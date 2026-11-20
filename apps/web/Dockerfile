# Etapa 1: build de Vite. Las variables VITE_* se incrustan en el JS en este momento,
# así que VITE_API_URL tiene que ser una URL que resuelva el navegador, no el nombre del servicio.
FROM node:26-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
ARG VITE_API_URL=http://localhost:8000
ARG VITE_USE_MOCKS=false
ENV VITE_API_URL=$VITE_API_URL \
    VITE_USE_MOCKS=$VITE_USE_MOCKS
RUN npm run build

# Etapa 2: nginx sirve los estáticos
FROM nginx:1.27-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 8080
