"""
Flask REST API Blueprint for Invoice OCR Service
Provides comprehensive OCR and invoice extraction endpoints
"""

import os
import uuid
import time
import json
import redis
from datetime import datetime
from typing import Dict, Any, Optional

from flask import Blueprint, request, jsonify, current_app, send_from_directory
from flask_jwt_extended import jwt_required, get_jwt_identity
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from marshmallow import ValidationError
from werkzeug.utils import secure_filename

from config import get_config
from models import (
    OCRProcessRequestSchema, InvoiceExtractRequestSchema, FileUploadSchema,
    create_success_response, create_error_response, create_paginated_response,
    validate_file_extension, validate_file_size
)
from ocr_processor import process_ocr
from invoice_extractor import extract_structured_from_text

# Create Blueprint
api_bp = Blueprint('api_v1', __name__, url_prefix='/api/v1')

# Initialize Redis client
def get_redis_client():
    """Get Redis client instance."""
    config = get_config()
    return redis.StrictRedis.from_url(config.REDIS_URL, decode_responses=True)

# Initialize Rate Limiter
def get_limiter():
    """Get rate limiter instance."""
    config = get_config()
    return Limiter(
        get_remote_address,
        app=current_app,
        storage_uri=config.RATELIMIT_STORAGE_URL
    )


# ============================================================================
# Health Check Endpoints
# ============================================================================

@api_bp.route('/health', methods=['GET'])
def health_check():
    """
    Health check endpoint
    ---
    tags:
      - Health
    responses:
      200:
        description: Service is healthy
        schema:
          type: object
          properties:
            success:
              type: boolean
            data:
              type: object
              properties:
                status:
                  type: string
                version:
                  type: string
                uptime:
                  type: number
                services:
                  type: object
    """
    try:
        # Check Redis connection
        r = get_redis_client()
        redis_status = "healthy" if r.ping() else "unhealthy"
        
        # Check Azure OpenAI configuration
        config = get_config()
        azure_status = "configured" if config.AZURE_OPENAI_KEY else "not_configured"
        
        health_data = {
            "status": "healthy",
            "version": config.VERSION,
            "uptime": time.time() - current_app.start_time if hasattr(current_app, 'start_time') else 0,
            "services": {
                "redis": redis_status,
                "azure_openai": azure_status
            }
        }
        
        return jsonify(create_success_response(health_data, "Service is healthy")), 200
        
    except Exception as e:
        return jsonify(create_error_response("Health check failed", "HEALTH_CHECK_ERROR", {"error": str(e)})), 500


# ============================================================================
# OCR Processing Endpoints
# ============================================================================

@api_bp.route('/ocr/process', methods=['POST'])
@jwt_required()
def process_ocr_endpoint():
    """
    Process OCR on uploaded file
    ---
    tags:
      - OCR
    security:
      - Bearer: []
    consumes:
      - multipart/form-data
    parameters:
      - in: formData
        name: file
        type: file
        required: true
        description: File to process (PDF, PNG, JPG, etc.)
      - in: formData
        name: language
        type: string
        default: en
        enum: [en, ch, fr, german, korean, japan]
        description: OCR language
      - in: formData
        name: use_gpu
        type: boolean
        default: false
        description: Use GPU acceleration
      - in: formData
        name: return_annotated_images
        type: boolean
        default: false
        description: Return annotated images
    responses:
      202:
        description: OCR processing started
        schema:
          type: object
          properties:
            success:
              type: boolean
            data:
              type: object
              properties:
                task_id:
                  type: string
                status:
                  type: string
                message:
                  type: string
      400:
        description: Bad request
      401:
        description: Unauthorized
      413:
        description: File too large
    """
    try:
        # Validate form data
        schema = OCRProcessRequestSchema()
        form_data = {
            'language': request.form.get('language', 'en'),
            'use_gpu': request.form.get('use_gpu', 'false').lower() in ['true', '1', 'yes', 'on'],
            'return_annotated_images': request.form.get('return_annotated_images', 'false').lower() in ['true', '1', 'yes', 'on']
        }
        
        try:
            validated_data = schema.load(form_data)
        except ValidationError as err:
            return jsonify(create_error_response("Validation failed", "VALIDATION_ERROR", err.messages)), 400
        
        # Check file upload
        if 'file' not in request.files:
            return jsonify(create_error_response("No file provided", "NO_FILE")), 400
        
        file = request.files['file']
        if not file or file.filename == '':
            return jsonify(create_error_response("No file selected", "EMPTY_FILENAME")), 400
        
        # Validate file
        config = get_config()
        if not validate_file_extension(file.filename, config.ALLOWED_EXTENSIONS):
            return jsonify(create_error_response(
                f"Unsupported file type. Allowed: {', '.join(config.ALLOWED_EXTENSIONS)}", 
                "INVALID_FILE_TYPE"
            )), 400
        
        # Check file size
        file.seek(0, 2)  # Seek to end
        file_size = file.tell()
        file.seek(0)  # Reset to beginning
        
        if not validate_file_size(file_size, config.MAX_CONTENT_LENGTH):
            return jsonify(create_error_response(
                f"File too large. Maximum size: {config.MAX_CONTENT_LENGTH // (1024*1024)}MB", 
                "FILE_TOO_LARGE"
            )), 413
        
        # Save file
        base_name = os.path.splitext(file.filename)[0] or "upload"
        safe_base = secure_filename(base_name)
        ext = os.path.splitext(file.filename)[1]
        unique_suffix = f"{int(time.time())}_{uuid.uuid4().hex[:8]}"
        filename = f"{safe_base}_{unique_suffix}{ext}"
        upload_path = os.path.join(config.UPLOAD_FOLDER, filename)
        
        file.save(upload_path)
        
        # Create task
        task_id = uuid.uuid4().hex
        r = get_redis_client()
        
        task_data = {
            "task_id": task_id,
            "status": "processing",
            "filename": filename,
            "language": validated_data.get("language", "en"),
            "use_gpu": json.dumps(validated_data.get("use_gpu", False)),
            "return_annotated_images": json.dumps(validated_data.get("return_annotated_images", False)),
            "created_at": datetime.utcnow().isoformat(),
            "user_id": get_jwt_identity().get("api_key_id", "unknown")
        }
        
        r.hset(f"task:{task_id}", mapping=task_data)
        
        # Start background processing
        try:
            from ..celery_worker import celery_app
            if celery_app:
                # Use Celery for background processing
                async_result = celery_app.send_task(
                    "tasks.ocr_process",
                    args=[upload_path, config.OUTPUT_FOLDER, validated_data.get("language", "en"), 
                          validated_data.get("use_gpu", False), validated_data.get("return_annotated_images", False)],
                    task_id=task_id
                )
                r.hset(f"task:{task_id}", "celery_task_id", async_result.id)
            else:
                # Fallback to threading
                import threading
                
                def process_task():
                    try:
                        results = process_ocr(
                            upload_path, 
                            config.OUTPUT_FOLDER, 
                            lang=validated_data.get("language", "en"), 
                            use_gpu=validated_data.get("use_gpu", False)
                        )
                        
                        result_data = {
                            "detected_texts": results,
                            "all_text": "\n".join(results),
                            "processing_time": time.time(),
                            "pages_processed": len(results)
                        }
                        
                        r.hset(f"task:{task_id}", "status", "completed")
                        r.set(f"task:{task_id}:result", json.dumps(result_data))
                        
                    except Exception as e:
                        r.hset(f"task:{task_id}", mapping={
                            "status": "failed",
                            "error": str(e),
                            "failed_at": datetime.utcnow().isoformat()
                        })
                
                thread = threading.Thread(target=process_task, daemon=True)
                thread.start()
                
        except Exception as e:
            r.hset(f"task:{task_id}", mapping={
                "status": "failed",
                "error": f"Failed to start processing: {str(e)}",
                "failed_at": datetime.utcnow().isoformat()
            })
        
        response_data = {
            "task_id": task_id,
            "status": "processing",
            "message": "OCR processing started"
        }
        
        return jsonify(create_success_response(response_data, "OCR processing started")), 202
        
    except Exception as e:
        return jsonify(create_error_response("Internal server error", "INTERNAL_ERROR", {"error": str(e)})), 500


@api_bp.route('/ocr/status/<task_id>', methods=['GET'])
@jwt_required()
def get_ocr_status(task_id: str):
    """
    Get OCR processing status
    ---
    tags:
      - OCR
    security:
      - Bearer: []
    parameters:
      - in: path
        name: task_id
        type: string
        required: true
        description: Task ID
    responses:
      200:
        description: Status retrieved successfully
      404:
        description: Task not found
    """
    try:
        r = get_redis_client()
        task_data = r.hgetall(f"task:{task_id}")
        
        if not task_data:
            return jsonify(create_error_response("Task not found", "TASK_NOT_FOUND")), 404
        
        # Check if task belongs to current user
        current_user = get_jwt_identity().get("api_key_id", "unknown")
        if task_data.get("user_id") != current_user:
            return jsonify(create_error_response("Access denied", "ACCESS_DENIED")), 403
        
        # Check Celery status if applicable
        if task_data.get("status") == "processing" and task_data.get("celery_task_id"):
            try:
                from ..celery_worker import celery_app
                if celery_app:
                    async_result = celery_app.AsyncResult(task_data["celery_task_id"])
                    if async_result.successful():
                        result = async_result.result
                        r.hset(f"task:{task_id}", "status", "completed")
                        r.set(f"task:{task_id}:result", json.dumps(result))
                        task_data["status"] = "completed"
                    elif async_result.failed():
                        r.hset(f"task:{task_id}", mapping={
                            "status": "failed",
                            "error": str(async_result.result),
                            "failed_at": datetime.utcnow().isoformat()
                        })
                        task_data["status"] = "failed"
                        task_data["error"] = str(async_result.result)
            except Exception:
                pass
        
        response_data = {
            "task_id": task_id,
            "status": task_data.get("status", "unknown"),
            "progress": task_data.get("progress", 0),
            "created_at": task_data.get("created_at"),
            "error_message": task_data.get("error")
        }
        
        return jsonify(create_success_response(response_data)), 200
        
    except Exception as e:
        return jsonify(create_error_response("Internal server error", "INTERNAL_ERROR", {"error": str(e)})), 500


@api_bp.route('/ocr/result/<task_id>', methods=['GET'])
@jwt_required()
def get_ocr_result(task_id: str):
    """
    Get OCR processing results
    ---
    tags:
      - OCR
    security:
      - Bearer: []
    parameters:
      - in: path
        name: task_id
        type: string
        required: true
        description: Task ID
    responses:
      200:
        description: Results retrieved successfully
      404:
        description: Task not found
      202:
        description: Task still processing
    """
    try:
        r = get_redis_client()
        task_data = r.hgetall(f"task:{task_id}")
        
        if not task_data:
            return jsonify(create_error_response("Task not found", "TASK_NOT_FOUND")), 404
        
        # Check if task belongs to current user
        current_user = get_jwt_identity().get("api_key_id", "unknown")
        if task_data.get("user_id") != current_user:
            return jsonify(create_error_response("Access denied", "ACCESS_DENIED")), 403
        
        status = task_data.get("status", "unknown")
        
        if status == "processing":
            return jsonify(create_success_response({
                "task_id": task_id,
                "status": "processing",
                "message": "Task is still processing"
            })), 202
        
        if status == "failed":
            return jsonify(create_error_response(
                task_data.get("error", "Processing failed"), 
                "PROCESSING_FAILED"
            )), 500
        
        if status == "completed":
            result_data = r.get(f"task:{task_id}:result")
            if result_data:
                try:
                    results = json.loads(result_data)
                    response_data = {
                        "task_id": task_id,
                        "status": "completed",
                        "results": results
                    }
                    return jsonify(create_success_response(response_data)), 200
                except json.JSONDecodeError:
                    return jsonify(create_error_response("Invalid result data", "INVALID_RESULT")), 500
        
        return jsonify(create_error_response("Unknown task status", "UNKNOWN_STATUS")), 500
        
    except Exception as e:
        return jsonify(create_error_response("Internal server error", "INTERNAL_ERROR", {"error": str(e)})), 500


# ============================================================================
# Invoice Extraction Endpoints
# ============================================================================

@api_bp.route('/invoice/extract', methods=['POST'])
@jwt_required()
def extract_invoice_data():
    """
    Extract structured invoice data from OCR results
    ---
    tags:
      - Invoice
    security:
      - Bearer: []
    parameters:
      - in: body
        name: request
        required: true
        schema:
          type: object
          properties:
            task_id:
              type: string
              description: OCR task ID
            page_number:
              type: integer
              description: Specific page to extract (optional)
    responses:
      200:
        description: Invoice data extracted successfully
      400:
        description: Bad request
      404:
        description: Task or result not found
    """
    try:
        # Validate request
        schema = InvoiceExtractRequestSchema()
        try:
            payload = schema.load(request.get_json(force=True))
        except ValidationError as err:
            return jsonify(create_error_response("Validation failed", "VALIDATION_ERROR", err.messages)), 400
        
        task_id = payload["task_id"]
        page_number = payload.get("page_number")
        
        # Get task data
        r = get_redis_client()
        task_data = r.hgetall(f"task:{task_id}")
        
        if not task_data:
            return jsonify(create_error_response("Task not found", "TASK_NOT_FOUND")), 404
        
        # Check if task belongs to current user
        current_user = get_jwt_identity().get("api_key_id", "unknown")
        if task_data.get("user_id") != current_user:
            return jsonify(create_error_response("Access denied", "ACCESS_DENIED")), 403
        
        # Check if task is completed
        if task_data.get("status") != "completed":
            return jsonify(create_error_response("Task not completed yet", "TASK_NOT_COMPLETED")), 400
        
        # Get OCR results
        result_data = r.get(f"task:{task_id}:result")
        if not result_data:
            return jsonify(create_error_response("OCR results not found", "RESULTS_NOT_FOUND")), 404
        
        try:
            ocr_results = json.loads(result_data)
        except json.JSONDecodeError:
            return jsonify(create_error_response("Invalid OCR results", "INVALID_RESULTS")), 500
        
        # Extract invoice data
        detected_texts = ocr_results.get("detected_texts", [])
        
        if page_number:
            # Extract from specific page
            if page_number > len(detected_texts):
                return jsonify(create_error_response("Page number out of range", "PAGE_OUT_OF_RANGE")), 400
            
            page_text = detected_texts[page_number - 1]
            try:
                invoice_data = extract_structured_from_text(page_text)
                invoice_data["page_number"] = page_number
                results = [invoice_data]
            except Exception as e:
                return jsonify(create_error_response(f"Extraction failed: {str(e)}", "EXTRACTION_FAILED")), 500
        else:
            # Extract from all pages
            results = []
            for idx, page_text in enumerate(detected_texts, 1):
                try:
                    invoice_data = extract_structured_from_text(page_text)
                    invoice_data["page_number"] = idx
                    results.append(invoice_data)
                except Exception as e:
                    # Continue with other pages even if one fails
                    results.append({
                        "invoice_number": "",
                        "invoice_date": "",
                        "vendor_name": "",
                        "customer_name": "",
                        "total_amount": "",
                        "tax_amount": "",
                        "page_number": idx,
                        "error": str(e)
                    })
        
        response_data = {
            "task_id": task_id,
            "invoice_data": results,
            "total_pages": len(detected_texts),
            "extraction_time": time.time()
        }
        
        return jsonify(create_success_response(response_data, "Invoice data extracted successfully")), 200
        
    except Exception as e:
        return jsonify(create_error_response("Internal server error", "INTERNAL_ERROR", {"error": str(e)})), 500


# ============================================================================
# File Management Endpoints
# ============================================================================

@api_bp.route('/files/<task_id>/download/<filename>', methods=['GET'])
@jwt_required()
def download_file(task_id: str, filename: str):
    """
    Download processed file
    ---
    tags:
      - Files
    security:
      - Bearer: []
    parameters:
      - in: path
        name: task_id
        type: string
        required: true
        description: Task ID
      - in: path
        name: filename
        type: string
        required: true
        description: Filename to download
    responses:
      200:
        description: File downloaded successfully
      404:
        description: File not found
    """
    try:
        # Verify task ownership
        r = get_redis_client()
        task_data = r.hgetall(f"task:{task_id}")
        
        if not task_data:
            return jsonify(create_error_response("Task not found", "TASK_NOT_FOUND")), 404
        
        current_user = get_jwt_identity().get("api_key_id", "unknown")
        if task_data.get("user_id") != current_user:
            return jsonify(create_error_response("Access denied", "ACCESS_DENIED")), 403
        
        # Check if file exists
        config = get_config()
        file_path = os.path.join(config.OUTPUT_FOLDER, filename)
        
        if not os.path.exists(file_path):
            return jsonify(create_error_response("File not found", "FILE_NOT_FOUND")), 404
        
        return send_from_directory(config.OUTPUT_FOLDER, filename, as_attachment=True)
        
    except Exception as e:
        return jsonify(create_error_response("Internal server error", "INTERNAL_ERROR", {"error": str(e)})), 500


# ============================================================================
# Task Management Endpoints
# ============================================================================

@api_bp.route('/tasks', methods=['GET'])
@jwt_required()
def list_tasks():
    """
    List user's tasks
    ---
    tags:
      - Tasks
    security:
      - Bearer: []
    parameters:
      - in: query
        name: page
        type: integer
        default: 1
        description: Page number
      - in: query
        name: per_page
        type: integer
        default: 20
        description: Items per page
      - in: query
        name: status
        type: string
        enum: [processing, completed, failed]
        description: Filter by status
    responses:
      200:
        description: Tasks retrieved successfully
    """
    try:
        # Get pagination parameters
        page = int(request.args.get('page', 1))
        per_page = min(int(request.args.get('per_page', 20)), 100)
        status_filter = request.args.get('status')
        
        # Get current user
        current_user = get_jwt_identity().get("api_key_id", "unknown")
        
        # Get user's tasks
        r = get_redis_client()
        task_keys = r.keys(f"task:*")
        
        tasks = []
        for key in task_keys:
            task_data = r.hgetall(key)
            if task_data.get("user_id") == current_user:
                if not status_filter or task_data.get("status") == status_filter:
                    tasks.append({
                        "task_id": task_data.get("task_id", key.split(":")[-1]),
                        "status": task_data.get("status", "unknown"),
                        "filename": task_data.get("filename", ""),
                        "created_at": task_data.get("created_at"),
                        "language": task_data.get("language", "en")
                    })
        
        # Sort by creation time (newest first)
        tasks.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        
        # Paginate
        total = len(tasks)
        start = (page - 1) * per_page
        end = start + per_page
        paginated_tasks = tasks[start:end]
        
        response_data = create_paginated_response(paginated_tasks, page, per_page, total)
        return jsonify(response_data), 200
        
    except Exception as e:
        return jsonify(create_error_response("Internal server error", "INTERNAL_ERROR", {"error": str(e)})), 500


@api_bp.route('/tasks/<task_id>', methods=['DELETE'])
@jwt_required()
def delete_task(task_id: str):
    """
    Delete a task and its associated files
    ---
    tags:
      - Tasks
    security:
      - Bearer: []
    parameters:
      - in: path
        name: task_id
        type: string
        required: true
        description: Task ID to delete
    responses:
      200:
        description: Task deleted successfully
      404:
        description: Task not found
    """
    try:
        # Verify task ownership
        r = get_redis_client()
        task_data = r.hgetall(f"task:{task_id}")
        
        if not task_data:
            return jsonify(create_error_response("Task not found", "TASK_NOT_FOUND")), 404
        
        current_user = get_jwt_identity().get("api_key_id", "unknown")
        if task_data.get("user_id") != current_user:
            return jsonify(create_error_response("Access denied", "ACCESS_DENIED")), 403
        
        # Delete task data
        r.delete(f"task:{task_id}")
        r.delete(f"task:{task_id}:result")
        
        # Delete associated files
        config = get_config()
        filename = task_data.get("filename", "")
        if filename:
            # Delete uploaded file
            upload_path = os.path.join(config.UPLOAD_FOLDER, filename)
            if os.path.exists(upload_path):
                os.remove(upload_path)
            
            # Delete output files
            base_name = os.path.splitext(filename)[0]
            for ext in ['.txt', '.json', '.png']:
                output_file = os.path.join(config.OUTPUT_FOLDER, f"{base_name}{ext}")
                if os.path.exists(output_file):
                    os.remove(output_file)
        
        return jsonify(create_success_response(None, "Task deleted successfully")), 200
        
    except Exception as e:
        return jsonify(create_error_response("Internal server error", "INTERNAL_ERROR", {"error": str(e)})), 500


# ============================================================================
# Error Handlers
# ============================================================================

@api_bp.errorhandler(400)
def bad_request(error):
    """Handle 400 Bad Request errors."""
    return jsonify(create_error_response("Bad request", "BAD_REQUEST")), 400


@api_bp.errorhandler(401)
def unauthorized(error):
    """Handle 401 Unauthorized errors."""
    return jsonify(create_error_response("Unauthorized", "UNAUTHORIZED")), 401


@api_bp.errorhandler(403)
def forbidden(error):
    """Handle 403 Forbidden errors."""
    return jsonify(create_error_response("Access denied", "FORBIDDEN")), 403


@api_bp.errorhandler(404)
def not_found(error):
    """Handle 404 Not Found errors."""
    return jsonify(create_error_response("Resource not found", "NOT_FOUND")), 404


@api_bp.errorhandler(413)
def file_too_large(error):
    """Handle 413 File Too Large errors."""
    return jsonify(create_error_response("File too large", "FILE_TOO_LARGE")), 413


@api_bp.errorhandler(500)
def internal_error(error):
    """Handle 500 Internal Server errors."""
    return jsonify(create_error_response("Internal server error", "INTERNAL_ERROR")), 500
