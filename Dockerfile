# AETHER CareOps Platform — Multi-stage Docker Build
# Stage 1: Build React dashboard
# Stage 2: Python runtime with FastAPI + built dashboard

# ── Stage 1: Build Dashboard ──────────────────────────────────────────
FROM node:20-slim AS frontend-build
WORKDIR /app/dashboard
COPY dashboard/package.json dashboard/package-lock.json* ./
RUN npm install --no-audit
COPY dashboard/ ./
RUN npm run build

# ── Stage 2: Python Runtime ──────────────────────────────────────────
FROM python:3.11-slim
WORKDIR /app

# Install Python dependencies
RUN pip install --no-cache-dir fastapi uvicorn[standard] boto3

# Copy backend
COPY api/ /app/api/

# Copy built dashboard
COPY --from=frontend-build /app/dashboard/dist /app/dashboard/dist

# Copy .env.example as fallback (actual env vars come from App Runner/ECS)
COPY .env.example /app/.env.example

# Expose port
ENV PORT=8080
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/api/health')"

# Start server
CMD ["python", "api/server.py"]
