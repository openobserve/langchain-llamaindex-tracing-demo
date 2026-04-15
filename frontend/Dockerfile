FROM python:3.11-slim

WORKDIR /app

COPY . .

EXPOSE 3000
CMD sh -c 'printf "{\"BACKEND_URL\":\"%s\"}" "${BACKEND_URL:-http://localhost:8001}" > config.json && python3 -m http.server 3000'
