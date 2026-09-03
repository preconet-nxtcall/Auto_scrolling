# Production Dockerfile for Document Auto-Viewer SaaS
FROM python:3.11-slim

# Environment settings
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV HOST=0.0.0.0
ENV PORT=8000

# Install headless LibreOffice, fonts, and system libraries for Office/PDF/Image processing
RUN apt-get update && apt-get install -y --no-install-recommends \
    libreoffice \
    fonts-dejavu-core \
    fonts-liberation \
    curl \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Set container working directory
WORKDIR /app

# Copy dependencies and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project code
COPY . .

# Ensure runtime storage directories exist
RUN mkdir -p backend/storage/uploads backend/storage/converted backend/storage/temp

# Expose port
EXPOSE 8000

# Launch server
CMD ["python", "run.py"]
