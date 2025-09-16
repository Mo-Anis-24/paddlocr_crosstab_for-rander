# Invoice OCR REST API

A comprehensive Flask REST API for invoice OCR processing and structured data extraction using PaddleOCR and Azure OpenAI.

## 🚀 Features

- **OCR Processing**: Extract text from PDF, PNG, JPG, and other image formats
- **Invoice Data Extraction**: Use Azure OpenAI to extract structured invoice data
- **RESTful API**: Complete REST API with proper HTTP status codes
- **Authentication**: JWT-based authentication with API key support
- **Rate Limiting**: Configurable rate limiting for API endpoints
- **CORS Support**: Cross-origin resource sharing for frontend integration
- **Swagger Documentation**: Auto-generated API documentation
- **Background Processing**: Asynchronous task processing with Celery
- **File Management**: Upload, process, and download files
- **Error Handling**: Comprehensive error handling with consistent response format

## 📋 Table of Contents

- Installation
- Configuration
- API Endpoints
- Authentication
- Usage Examples
- Frontend Integration
- Deployment
- Testing
- Troubleshooting

## 🛠 Installation

Prerequisites: Python 3.8+, Redis, Azure OpenAI account.

1. Clone repo, create venv, install requirements.
2. Create .env with required variables.
3. Run `python app.py` (full API) or `python simple_api.py` (simple API).

## 🔗 API Endpoints (Full API base: http://localhost:5000/api/v1)
- POST /auth/token
- GET /health
- POST /ocr/process
- GET /ocr/status/{task_id}
- GET /ocr/result/{task_id}
- POST /invoice/extract
- GET /tasks
- DELETE /tasks/{task_id}
- GET /files/{task_id}/download/{filename}

Includes request/response examples and cURL snippets in the original doc.

## 📚 Swagger UI
- http://localhost:5000/apidocs

## 🧪 Testing
- pytest commands included in the original doc.

## 🚀 Docker
- `docker build -t invoice-ocr-api .`
- `docker-compose up -d`

See the original full text for details; this is relocated under docs/.
