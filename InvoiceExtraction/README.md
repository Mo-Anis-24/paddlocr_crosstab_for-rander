# Invoice Extraction with OCR and AI

A powerful web application that extracts text from PDFs and images using PaddleOCR, then uses Azure OpenAI to intelligently extract structured invoice data into Excel format.

## Features

- **OCR Processing**: Extract text from PDFs and images using PaddleOCR with GPU acceleration
- **Visualization**: See how PaddleOCR detects text with annotated preview images
- **AI-Powered Extraction**: Use Azure OpenAI to extract structured invoice data
- **Multi-page Support**: Process multi-page PDFs with page-wise Excel output
- **Excel Export**: Generate structured Excel files with invoice details
- **Web Interface**: Easy-to-use web interface for file upload and processing

## Prerequisites

- Python 3.10+ (tested with Python 3.10.11)
- Windows 10/11 (tested on Windows 10)
- GPU support (optional but recommended for faster OCR)

## Installation

### 1. Clone or Download the Project

```bash
# If you have git
git clone <repository-url>
cd "invoice extraction clon repo/InvoiceExtraction"

# Or download and extract the ZIP file
```

### 2. Create Virtual Environment

```powershell
# Navigate to the project directory
cd "C:\Users\ANIS MANSURI\Downloads\invoice extraction clon repo\InvoiceExtraction"

# Create virtual environment
python -m venv invoice_env

# Activate virtual environment
.\invoice_env\Scripts\Activate.ps1
```

### 3. Install Dependencies

```powershell
# Make sure virtual environment is activated
.\invoice_env\Scripts\Activate.ps1

# Install required packages
pip install -r requirements.txt
```

### 4. Configure Azure OpenAI (Optional)

Edit the credentials in `app.py` at the top of the file:

```python
# ============================
# Azure OpenAI Credentials
# ============================
AZURE_OPENAI_ENDPOINT_CFG = "https://your-resource.openai.azure.com/"
AZURE_OPENAI_KEY_CFG = "your-azure-openai-key"
AZURE_DEPLOYMENT_NAME_CFG = "gpt-4o"
```

Or set environment variables:

```powershell
$env:AZURE_OPENAI_ENDPOINT="https://your-resource.openai.azure.com/"
$env:AZURE_OPENAI_KEY="your-azure-openai-key"
$env:AZURE_DEPLOYMENT_NAME="gpt-4o"
```

## Running the Application

### Method 1: Using Virtual Environment

```powershell
# Navigate to project directory
cd "C:\Users\ANIS MANSURI\Downloads\invoice extraction clon repo\InvoiceExtraction"

# Activate virtual environment
.\invoice_env\Scripts\Activate.ps1

# Run the application
python app.py
```

### Method 2: Using Environment Variables

```powershell
# Navigate to project directory
cd "C:\Users\ANIS MANSURI\Downloads\invoice extraction clon repo\InvoiceExtraction"

# Set environment variables (optional)
$env:AZURE_OPENAI_ENDPOINT="https://conversationalanalytics.openai.azure.com/"
$env:AZURE_OPENAI_KEY="5eeb9c3360ce4b158390108abc7e4f1a"
$env:AZURE_DEPLOYMENT_NAME="gpt-4o"

# Activate virtual environment and run
.\invoice_env\Scripts\Activate.ps1
python app.py
```

### Method 3: One-liner Command

```powershell
cd "C:\Users\ANIS MANSURI\Downloads\invoice extraction clon repo\InvoiceExtraction"; $env:AZURE_OPENAI_ENDPOINT="https://conversationalanalytics.openai.azure.com/"; $env:AZURE_OPENAI_KEY="5eeb9c3360ce4b158390108abc7e4f1a"; $env:AZURE_DEPLOYMENT_NAME="gpt-4o"; .\invoice_env\Scripts\python.exe app.py
```

## Using the Application

### 1. Access the Web Interface

Once the application is running, open your web browser and go to:
- **Local**: http://127.0.0.1:5000
- **Network**: http://192.168.1.4:5000 (if accessible from other devices)

### 2. Upload and Process Files

1. **Select File**: Drag and drop or click to browse for PDF/image files
2. **Choose Language**: Select OCR language(s) - English is selected by default
3. **GPU Acceleration**: Check "Use GPU acceleration" for faster processing (recommended)
4. **Run OCR**: Click "Run OCR" to process the file

### 3. View Results

After processing, you'll see:

- **Detected Text Regions**: List of all text found with confidence scores
- **All Extracted Text**: Complete text content from the document
- **OCR Visualizations**: Images showing how PaddleOCR detected text (green boxes)
- **Download Options**: 
  - Download text as .txt file
  - Generate Excel with structured invoice data (requires Azure OpenAI)

### 4. Generate Excel Report

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

## Project Structure

```
InvoiceExtraction/
├── app.py                 # Main Flask application
├── requirements.txt       # Python dependencies
├── README.md             # This manual
├── templates/
│   ├── index.html        # Upload page
│   └── result.html       # Results page
├── uploads/              # Uploaded files (auto-created)
├── outputs/              # Processed files (auto-created)
├── invoice_env/          # Virtual environment
└── PaddleOCR/            # PaddleOCR repository
```

## Troubleshooting

### Common Issues

1. **"File not selected" error**
   - Make sure you're in the correct directory: `InvoiceExtraction/`
   - Check that the file format is supported

2. **PaddleOCR initialization errors**
   - Ensure all dependencies are installed: `pip install -r requirements.txt`
   - Try running without GPU: uncheck "Use GPU acceleration"

3. **"Missing pages payload" error**
   - Refresh the results page and try "Generate Excel" again
   - Make sure Azure OpenAI credentials are configured

4. **Azure OpenAI errors**
   - Verify your credentials in `app.py` or environment variables
   - Check that your Azure OpenAI deployment is active
   - Ensure you have sufficient quota

### Performance Tips

- **Use GPU acceleration** for faster OCR processing
- **Smaller files** process faster than larger ones
- **Single language** selection is faster than multiple languages
- **Close other applications** to free up system resources

## Dependencies

- **paddleocr==2.7.0.3**: OCR engine
- **opencv-python==4.6.0.66**: Image processing
- **Flask==3.0.3**: Web framework
- **pypdfium2==4.30.0**: PDF processing
- **pandas==2.2.2**: Data manipulation
- **openpyxl==3.1.5**: Excel file creation
- **python-dotenv==1.0.1**: Environment variable loading

## API Endpoints

- `GET /`: Upload page
- `POST /ocr`: Process uploaded files
- `POST /extract-excel`: Generate Excel from OCR results
- `GET /uploads/<filename>`: Serve uploaded files
- `GET /outputs/<filename>`: Serve processed files

## License

This project is for educational and personal use. Please ensure you comply with the licenses of all dependencies, especially PaddleOCR and Azure OpenAI.

## Support

For issues and questions:
1. Check this README first
2. Verify all dependencies are installed correctly
3. Check the console output for error messages
4. Ensure you're running from the correct directory

## Version

- **Version**: 1.0
- **Python**: 3.10+
- **PaddleOCR**: 2.7.0.3
- **Flask**: 3.0.3

---

**Happy Invoice Processing!** 🚀