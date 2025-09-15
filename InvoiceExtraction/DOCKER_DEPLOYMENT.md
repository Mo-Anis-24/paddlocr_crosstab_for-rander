# Docker Deployment Guide for Invoice Extraction App

This guide provides step-by-step instructions to run the Invoice Extraction Flask application using Docker while preserving all functionality and models.

## Prerequisites

- Docker Desktop installed on your system
- Docker Compose (included with Docker Desktop)
- Basic knowledge of command line operations

## Quick Start

### 1. Navigate to the Project Directory

```bash
cd "InvoiceExtraction"
```

### 2. Set Up Environment Variables

Copy the example environment file and configure your Azure OpenAI credentials:

```bash
# Windows
copy env.example .env

# Linux/Mac
cp env.example .env
```

Edit the `.env` file with your Azure OpenAI credentials:

```env
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_KEY=your-azure-openai-key-here
AZURE_DEPLOYMENT_NAME=gpt-4o
AZURE_OPENAI_API_VERSION=2024-08-01-preview
FLASK_SECRET_KEY=your-secret-key-change-in-production
PORT=5000
```

### 3. Build and Run with Docker Compose

```bash
# Build and start the application
docker-compose up --build

# Or run in detached mode (background)
docker-compose up --build -d
```

### 4. Access the Application

Open your web browser and navigate to:
- **Local**: http://localhost:5000
- **Network**: http://your-ip-address:5000

## Alternative: Using Docker Commands Directly

### 1. Build the Docker Image

```bash
docker build -t invoice-extraction .
```

### 2. Run the Container

```bash
# With environment variables
docker run -d \
  --name invoice-extraction-app \
  -p 5000:5000 \
  -e AZURE_OPENAI_ENDPOINT="https://your-resource.openai.azure.com/" \
  -e AZURE_OPENAI_KEY="your-azure-openai-key" \
  -e AZURE_DEPLOYMENT_NAME="gpt-4o" \
  -e FLASK_SECRET_KEY="your-secret-key" \
  -v $(pwd)/uploads:/app/uploads \
  -v $(pwd)/outputs:/app/outputs \
  invoice-extraction
```

## Docker Configuration Details

### Dockerfile Features

- **Base Image**: Python 3.10 slim for optimal size and performance
- **System Dependencies**: Includes all required libraries for PaddleOCR and OpenCV
- **Python Dependencies**: Installs all requirements from requirements.txt
- **PaddleOCR Support**: Includes PaddlePaddle and additional ML libraries
- **Health Check**: Monitors application health
- **Security**: Non-root user execution and proper permissions

### Docker Compose Features

- **Environment Variables**: Easy configuration through .env file
- **Volume Mounting**: Persistent storage for uploads and outputs
- **Health Monitoring**: Automatic health checks
- **Port Mapping**: Exposes application on port 5000
- **Restart Policy**: Automatic restart on failure

## File Structure

```
InvoiceExtraction/
├── Dockerfile              # Docker image configuration
├── docker-compose.yml      # Docker Compose configuration
├── .dockerignore          # Files to ignore during build
├── env.example            # Environment variables template
├── DOCKER_DEPLOYMENT.md   # This deployment guide
├── app.py                 # Main Flask application
├── requirements.txt       # Python dependencies
├── templates/             # HTML templates
├── uploads/               # Uploaded files (created automatically)
└── outputs/               # Processed files (created automatically)
```

## Environment Variables

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `AZURE_OPENAI_ENDPOINT` | Azure OpenAI endpoint URL | - | Yes (for Excel generation) |
| `AZURE_OPENAI_KEY` | Azure OpenAI API key | - | Yes (for Excel generation) |
| `AZURE_DEPLOYMENT_NAME` | Azure OpenAI deployment name | gpt-4o | No |
| `AZURE_OPENAI_API_VERSION` | Azure OpenAI API version | 2024-08-01-preview | No |
| `FLASK_SECRET_KEY` | Flask secret key for sessions | dev-secret-key-change-in-production | No |
| `PORT` | Application port | 5000 | No |

## Usage Instructions

### 1. Upload and Process Files

1. **Select File**: Drag and drop or click to browse for PDF/image files
2. **Choose Language**: Select OCR language(s) - English is selected by default
3. **GPU Acceleration**: Check "Use GPU acceleration" for faster processing
4. **Run OCR**: Click "Run OCR" to process the file

### 2. View Results

After processing, you'll see:
- **Detected Text Regions**: List of all text found with confidence scores
- **All Extracted Text**: Complete text content from the document
- **OCR Visualizations**: Images showing how PaddleOCR detected text
- **Download Options**: 
  - Download text as .txt file
  - Generate Excel with structured invoice data (requires Azure OpenAI)

### 3. Generate Excel Report

If you have Azure OpenAI configured:
1. Click "Generate Excel" button
2. The system will extract structured data from each page
3. Download the Excel file with columns:
   - Page number
   - Invoice Number
   - Invoice Date
   - Vendor Name
   - Customer Name
   - Total Amount
   - Tax Amount

## Supported File Formats

- **PDF**: Multi-page PDF documents
- **Images**: PNG, JPEG, JPG, BMP, TIFF, TIF, WebP
- **Maximum file size**: 50 MB

## Management Commands

### View Logs

```bash
# View logs from docker-compose
docker-compose logs -f

# View logs from specific container
docker logs -f invoice-extraction-app
```

### Stop the Application

```bash
# Stop docker-compose
docker-compose down

# Stop specific container
docker stop invoice-extraction-app
```

### Restart the Application

```bash
# Restart docker-compose
docker-compose restart

# Restart specific container
docker restart invoice-extraction-app
```

### Update the Application

```bash
# Rebuild and restart
docker-compose up --build -d

# Or pull latest changes and rebuild
git pull
docker-compose up --build -d
```

### Clean Up

```bash
# Remove containers and networks
docker-compose down

# Remove containers, networks, and volumes
docker-compose down -v

# Remove images
docker rmi invoice-extraction
```

## Troubleshooting

### Common Issues

1. **Container won't start**
   - Check if port 5000 is already in use
   - Verify Docker is running
   - Check logs: `docker-compose logs`

2. **OCR not working**
   - Ensure all system dependencies are installed
   - Check if PaddleOCR models are downloading correctly
   - Try without GPU acceleration

3. **Azure OpenAI errors**
   - Verify credentials in .env file
   - Check Azure OpenAI deployment status
   - Ensure sufficient quota

4. **File upload issues**
   - Check file size (max 50MB)
   - Verify file format is supported
   - Check uploads directory permissions

### Performance Tips

- **Use GPU acceleration** for faster OCR processing (if available)
- **Smaller files** process faster than larger ones
- **Single language** selection is faster than multiple languages
- **Allocate sufficient memory** to Docker (recommended: 4GB+)

### Health Check

The application includes a health check that monitors:
- Application responsiveness
- Port availability
- Basic functionality

Check health status:
```bash
docker ps
# Look for "healthy" status in the STATUS column
```

## Production Deployment

### Security Considerations

1. **Change default secret key** in production
2. **Use HTTPS** with reverse proxy (nginx)
3. **Limit file upload size** based on your needs
4. **Regular security updates** for base image
5. **Monitor resource usage** and logs

### Scaling

For high-traffic scenarios:
1. Use multiple container instances
2. Implement load balancing
3. Use external storage for uploads/outputs
4. Consider GPU-enabled instances for faster OCR

### Monitoring

Monitor the application using:
- Docker health checks
- Application logs
- Resource usage (CPU, memory, disk)
- Response times

## Support

For issues and questions:
1. Check this deployment guide first
2. Verify Docker and Docker Compose installation
3. Check container logs for error messages
4. Ensure all environment variables are set correctly
5. Verify Azure OpenAI credentials and quota

---

**Happy Invoice Processing with Docker!** 🐳🚀


