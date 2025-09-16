# Use Python 3.10 slim image as base
FROM python:3.10-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV DEBIAN_FRONTEND=noninteractive
ENV FLASK_ENV=production
ENV PORT=5100

# Set working directory
WORKDIR /app

# Install system dependencies required for PaddleOCR and OpenCV
RUN apt-get update && apt-get install -y \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    libgcc-s1 \
    libgfortran5 \
    libopenblas-dev \
    liblapack-dev \
    gfortran \
    curl \
    wget \
    git \
    libglib2.0-dev \
    libgtk-3-dev \
    libavcodec-dev \
    libavformat-dev \
    libswscale-dev \
    libv4l-dev \
    libxvidcore-dev \
    libx264-dev \
    libjpeg-dev \
    libpng-dev \
    libtiff-dev \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create necessary directories
RUN mkdir -p uploads outputs

# Create non-root user
RUN useradd --create-home --shell /bin/bash app && \
    chown -R app:app /app

# Expose port
EXPOSE 5100

# ADD THIS NEW BLOCK
# Set the environment variable for the cache location
ENV PADDLEOCR_HOME=/home/app/.paddleocr

# Manually download, unpack the models, and set permissions (run as root)
RUN export DET_URL='https://paddleocr.bj.bcebos.com/PP-OCRv3/english/en_PP-OCRv3_det_infer.tar' && \
    export REC_URL='https://paddleocr.bj.bcebos.com/PP-OCRv3/english/en_PP-OCRv3_rec_infer.tar' && \
    export CLS_URL='https://paddleocr.bj.bcebos.com/PP-OCRv2/ch_ppocr_mobile_v2.0_cls_infer.tar' && \
    mkdir -p "$PADDLEOCR_HOME/whl/det/en/en_PP-OCRv3_det_infer" && \
    mkdir -p "$PADDLEOCR_HOME/whl/rec/en/en_PP-OCRv3_rec_infer" && \
    mkdir -p "$PADDLEOCR_HOME/whl/cls/ch_ppocr_mobile_v2.0_cls_infer" && \
    wget -O - ${DET_URL} | tar -C "$PADDLEOCR_HOME/whl/det/en/en_PP-OCRv3_det_infer" -x && \
    wget -O - ${REC_URL} | tar -C "$PADDLEOCR_HOME/whl/rec/en/en_PP-OCRv3_rec_infer" -x && \
    wget -O - ${CLS_URL} | tar -C "$PADDLEOCR_HOME/whl/cls/ch_ppocr_mobile_v2.0_cls_infer" -x && \
    chown -R app:app /home/app

# NOW, switch to the non-root user for the final command
USER app

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:5100/api/health || exit 1

# Run the simple API
CMD ["python", "simple_api.py"]


