# Backend Dockerfile for PDF to Excel Converter

FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Install system dependencies for PDF processing
# - ghostscript: Required by camelot-py for PDF rendering
# - python3-tk: Required by camelot-py
# - libgl1-mesa-glx, libglib2.0-0: OpenCV dependencies
# - default-jre: Required by tabula-py (Java runtime)
# - poppler-utils: Required by pdf2image for PDF to image conversion (provides pdfinfo)
# - tesseract-ocr: Required by pytesseract for OCR processing
RUN apt-get update && apt-get install -y --no-install-recommends \
    ghostscript \
    python3-tk \
    libgl1-mesa-glx \
    libglib2.0-0 \
    default-jre \
    libmagic1 \
    poppler-utils \
    tesseract-ocr \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements first for better Docker layer caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY ./app ./app

# Create directories for uploads and outputs
RUN mkdir -p uploads outputs

# Create non-root user for security
RUN adduser --disabled-password --gecos '' appuser && \
    chown -R appuser:appuser /app
USER appuser

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

# Run the application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
