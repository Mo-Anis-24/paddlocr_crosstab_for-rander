from marshmallow import Schema, fields, validate, post_load
from typing import Dict, Any, Optional


# ============================================================================
# Request Schemas
# ============================================================================

class AuthRequestSchema(Schema):
    """Schema for authentication requests."""
    api_key = fields.Str(
        required=True, 
        validate=validate.Length(min=8, max=100),
        error_messages={
            'required': 'API key is required',
            'invalid': 'API key must be between 8 and 100 characters'
        }
    )


class OCRProcessRequestSchema(Schema):
    """Schema for OCR processing requests."""
    language = fields.Str(
        required=False, 
        missing="en",
        validate=validate.OneOf(['en', 'ch', 'fr', 'german', 'korean', 'japan'],
                               error="Language must be one of: en, ch, fr, german, korean, japan")
    )
    use_gpu = fields.Bool(required=False, missing=False)
    return_annotated_images = fields.Bool(required=False, missing=False)


class InvoiceExtractRequestSchema(Schema):
    """Schema for invoice extraction requests."""
    task_id = fields.Str(
        required=True,
        validate=validate.Length(min=1, max=100),
        error_messages={'required': 'Task ID is required'}
    )
    page_number = fields.Int(
        required=False, 
        missing=None,
        validate=validate.Range(min=1, error="Page number must be positive")
    )


class FileUploadSchema(Schema):
    """Schema for file upload validation."""
    filename = fields.Str(required=True)
    content_type = fields.Str(required=True)
    size = fields.Int(required=True, validate=validate.Range(max=50*1024*1024))  # 50MB max


# ============================================================================
# Response Schemas
# ============================================================================

class BaseResponseSchema(Schema):
    """Base response schema with common fields."""
    success = fields.Bool(required=True)
    message = fields.Str(required=False)
    timestamp = fields.DateTime(required=False, format='iso')


class ErrorResponseSchema(BaseResponseSchema):
    """Schema for error responses."""
    success = fields.Bool(required=False, load_default=False)
    message = fields.Str(required=True)
    error_code = fields.Str(required=False)
    details = fields.Dict(required=False)


class SuccessResponseSchema(BaseResponseSchema):
    """Schema for success responses."""
    success = fields.Bool(required=False, load_default=True)
    data = fields.Raw(required=False)
    message = fields.Str(required=False)


class OCRStatusResponseSchema(BaseResponseSchema):
    """Schema for OCR status responses."""
    task_id = fields.Str(required=True)
    status = fields.Str(
        required=True,
        validate=validate.OneOf(['processing', 'completed', 'failed', 'pending'])
    )
    progress = fields.Int(required=False, validate=validate.Range(min=0, max=100))
    estimated_completion = fields.DateTime(required=False, format='iso')
    error_message = fields.Str(required=False)


class OCRResultResponseSchema(BaseResponseSchema):
    """Schema for OCR result responses."""
    task_id = fields.Str(required=True)
    status = fields.Str(required=True)
    results = fields.Dict(required=False)
    processing_time = fields.Float(required=False)
    pages_processed = fields.Int(required=False)
    confidence_scores = fields.List(fields.Float(), required=False)


class InvoiceDataSchema(Schema):
    """Schema for extracted invoice data."""
    invoice_number = fields.Str(required=False, missing="")
    invoice_date = fields.Str(required=False, missing="")
    vendor_name = fields.Str(required=False, missing="")
    customer_name = fields.Str(required=False, missing="")
    total_amount = fields.Str(required=False, missing="")
    tax_amount = fields.Str(required=False, missing="")
    page_number = fields.Int(required=False)
    confidence = fields.Float(required=False)


class InvoiceExtractResponseSchema(BaseResponseSchema):
    """Schema for invoice extraction responses."""
    task_id = fields.Str(required=True)
    invoice_data = fields.Nested(InvoiceDataSchema, many=True)
    total_pages = fields.Int(required=False)
    extraction_time = fields.Float(required=False)


class HealthResponseSchema(BaseResponseSchema):
    """Schema for health check responses."""
    status = fields.Str(required=True)
    version = fields.Str(required=False)
    uptime = fields.Float(required=False)
    services = fields.Dict(required=False)


class PaginationSchema(Schema):
    """Schema for pagination metadata."""
    page = fields.Int(required=True, validate=validate.Range(min=1))
    per_page = fields.Int(required=True, validate=validate.Range(min=1, max=100))
    total = fields.Int(required=True)
    pages = fields.Int(required=True)
    has_next = fields.Bool(required=True)
    has_prev = fields.Bool(required=True)


class PaginatedResponseSchema(BaseResponseSchema):
    """Schema for paginated responses."""
    data = fields.List(fields.Raw(), required=True)
    pagination = fields.Nested(PaginationSchema, required=True)


# ============================================================================
# Validation Helpers
# ============================================================================

def validate_file_extension(filename: str, allowed_extensions: set) -> bool:
    """Validate file extension against allowed extensions."""
    if not filename or '.' not in filename:
        return False
    ext = filename.rsplit('.', 1)[1].lower()
    return ext in allowed_extensions


def validate_file_size(file_size: int, max_size: int) -> bool:
    """Validate file size against maximum allowed size."""
    return file_size <= max_size


# ============================================================================
# Response Builders
# ============================================================================

def create_success_response(data: Any = None, message: str = "Operation successful") -> Dict[str, Any]:
    """Create a standardized success response."""
    return {
        "success": True,
        "data": data,
        "message": message
    }


def create_error_response(message: str, error_code: str = None, details: Dict = None) -> Dict[str, Any]:
    """Create a standardized error response."""
    response = {
        "success": False,
        "message": message
    }
    if error_code:
        response["error_code"] = error_code
    if details:
        response["details"] = details
    return response


def create_paginated_response(data: list, page: int, per_page: int, total: int) -> Dict[str, Any]:
    """Create a paginated response."""
    pages = (total + per_page - 1) // per_page
    return {
        "success": True,
        "data": data,
        "pagination": {
            "page": page,
            "per_page": per_page,
            "total": total,
            "pages": pages,
            "has_next": page < pages,
            "has_prev": page > 1
        }
    }




