# 📄 Invoice OCR API

A powerful REST API for extracting text and structured data from invoices using PaddleOCR and Azure OpenAI. This API can process PDFs and images to extract invoice information intelligently.

## 🚀 Features

- **OCR Processing**: Extract text from PDFs and images using PaddleOCR
- **Intelligent Extraction**: Use Azure OpenAI LLM for smart invoice data extraction
- **Multiple Formats**: Support for PDF, PNG, JPG, JPEG, BMP, TIFF, WEBP
- **RESTful API**: Clean REST endpoints for easy integration
- **Async Processing**: Background processing with task status tracking
- **Fallback Support**: Regex-based extraction if Azure LLM is unavailable

## 📋 API Endpoints

### Health Check
```
GET /api/health
```
Returns API status and configuration.

### OCR Processing
```
POST /api/ocr/process
```
Upload a file for OCR processing.

**Request Body (JSON):**
```json
{
    "file_path": "/path/to/your/file.pdf",
    "language": "en",
    "use_gpu": false
}
```

**Response:**
```json
{
    "task_id": "abc123def456789",
    "status": "processing",
    "message": "OCR processing started"
}
```

### Check Processing Status
```
GET /api/ocr/status/{task_id}
```
Check the status of OCR processing.

**Response:**
```json
{
    "task_id": "abc123def456789",
    "status": "completed",
    "error": null
}
```

### Get OCR Results
```
GET /api/ocr/result/{task_id}
```
Retrieve extracted text from OCR processing.

**Response:**
```json
{
    "task_id": "abc123def456789",
    "status": "completed",
    "results": {
        "detected_texts": ["Extracted text here"],
        "all_text": "All extracted text combined",
        "pages_processed": 1
    }
}
```

### Extract Invoice Data
```
POST /api/invoice/extract
```
Extract structured invoice data from OCR results.

**Request Body:**
```json
{
    "task_id": "abc123def456789"
}
```

**Response:**
```json
{
    "task_id": "abc123def456789",
    "invoice_data": {
        "invoice_number": "INV-001",
        "invoice_date": "2024-01-15",
        "vendor_name": "ABC Company",
        "customer_name": "XYZ Corp",
        "total_amount": "1,234.56",
        "tax_amount": "123.46",
        "_extraction_method": "azure_llm",
        "_extraction_status": "success"
    }
}
```

## 🛠️ Installation & Setup

### Prerequisites
- Python 3.8+
- Azure OpenAI account (for intelligent extraction)
- PaddleOCR dependencies

### 1. Clone Repository
```bash
git clone <your-repo-url>
cd InvoiceExtraction
```

### 2. Create Virtual Environment
```bash
python -m venv venv
# Windows
venv\Scripts\activate
# Linux/Mac
source venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure Azure OpenAI (Optional)
Create a `.env` file in the project root:
```env
AZURE_OPENAI_KEY=your_azure_openai_key_here
AZURE_OPENAI_ENDPOINT=https://your-resource-name.openai.azure.com/
AZURE_DEPLOYMENT_NAME=gpt-4o
AZURE_OPENAI_API_VERSION=2024-08-01-preview
```

### 5. Run the API
```bash
python simple_api.py
```

The API will start on `http://127.0.0.1:5100`

## 🔧 Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `AZURE_OPENAI_KEY` | Azure OpenAI API key | - |
| `AZURE_OPENAI_ENDPOINT` | Azure OpenAI endpoint URL | - |
| `AZURE_DEPLOYMENT_NAME` | Azure deployment name | `gpt-4o` |
| `AZURE_OPENAI_API_VERSION` | Azure API version | `2024-08-01-preview` |
| `PORT` | Server port | `5100` |
| `UPLOAD_FOLDER` | Upload directory | `./uploads` |
| `OUTPUT_FOLDER` | Output directory | `./outputs` |

### File Upload Limits
- **Maximum file size**: 50MB
- **Supported formats**: PDF, PNG, JPG, JPEG, BMP, TIFF, TIF, WEBP

## 📖 Usage Examples

### Python Example
```python
import requests

# Upload file for processing
response = requests.post('http://127.0.0.1:5100/api/ocr/process', 
                        json={
                            "file_path": "/path/to/invoice.pdf",
                            "language": "en",
                            "use_gpu": False
                        })
task_id = response.json()['task_id']

# Check status
status_response = requests.get(f'http://127.0.0.1:5100/api/ocr/status/{task_id}')
while status_response.json()['status'] == 'processing':
    time.sleep(2)
    status_response = requests.get(f'http://127.0.0.1:5100/api/ocr/status/{task_id}')

# Get results
results = requests.get(f'http://127.0.0.1:5100/api/ocr/result/{task_id}')
print(results.json())

# Extract invoice data
invoice_data = requests.post('http://127.0.0.1:5100/api/invoice/extract',
                            json={"task_id": task_id})
print(invoice_data.json())
```

## 🏗️ Project Structure
```
InvoiceExtraction/
├── simple_api.py          # Main API server
├── config.py              # Configuration settings
├── ocr_processor.py       # OCR processing logic
├── invoice_extractor.py   # Azure LLM extraction
├── models.py              # Data models
├── auth.py                # Authentication (for full API)
├── api_app.py             # Full API with auth
├── requirements.txt       # Python dependencies
├── uploads/               # File upload directory
├── outputs/               # OCR output directory
└── templates/             # HTML templates
```

## 🔍 API Variants
- Simple API (`simple_api.py`) on port 5100 (no auth)
- Full API (`api_app.py`) on port 8000 (JWT auth)
