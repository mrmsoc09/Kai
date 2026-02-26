FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
# System deps
RUN apt-get update -y && apt-get install -y build-essential curl && rm -rf /var/lib/apt/lists/*
# Copy requirements and install
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt
# Copy source
COPY . /app
ENV PYTHONPATH=/app
# Env defaults (override via compose)
ENV PORT=8080
EXPOSE 8080
CMD ["uvicorn", "apps.backend.src.main:app", "--host", "0.0.0.0", "--port", "8080"]
