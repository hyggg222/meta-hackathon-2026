# Shrimp size check: one image with Python (FastAPI) and the Node decoder for SAM masks.
# Build: docker build -t shrimp .
# Run:   docker run -d --name shrimp --restart unless-stopped --env-file .env \
#          -v /srv/shrimp-data:/app/data -p 80:8000 shrimp

FROM node:22-bookworm-slim AS node
WORKDIR /app/node
COPY node/package.json node/package-lock.json ./
RUN npm ci --omit=dev

FROM python:3.8-slim-bookworm
WORKDIR /app
COPY --from=node /usr/local/bin/node /usr/local/bin/node
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY shrimp ./shrimp
COPY node/package.json node/decode.mjs ./node/
COPY --from=node /app/node/node_modules ./node/node_modules
EXPOSE 8000
CMD ["uvicorn", "--factory", "shrimp.main:build", "--host", "0.0.0.0", "--port", "8000"]
