#!/usr/bin/env python3
import os
import time
import uuid
import threading
from typing import Dict, Any

from flask import Flask, jsonify, request
from werkzeug.utils import secure_filename

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    print("Warning: python-dotenv not installed. Install with: pip install python-dotenv")

from config import BaseConfig, ensure_directories
from ocr_processor import process_ocr
from invoice_extractor import extract_structured_from_text
import re


# In-memory task store for quick Postman testing (no Redis, no JWT)
TASKS: Dict[str, Dict[str, Any]] = {}


def create_app() -> Flask:
    app = Flask(__name__)
    app.config.from_object(BaseConfig)
    ensure_directories(BaseConfig)
    # Accept both with and without trailing slashes for routes
    app.url_map.strict_slashes = False
    
    # Debug: Check if Azure credentials are loaded
    azure_key = os.environ.get("AZURE_OPENAI_KEY", "")
    azure_endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT", "")
    azure_deployment = os.environ.get("AZURE_DEPLOYMENT_NAME", "")
    
    print(f"Azure Key loaded: {'Yes' if azure_key else 'No'}")
    print(f"Azure Endpoint loaded: {'Yes' if azure_endpoint else 'No'}")
    print(f"Azure Deployment loaded: {'Yes' if azure_deployment else 'No'}")
    
    if not azure_key or not azure_endpoint or not azure_deployment:
        print("WARNING: Azure credentials not fully configured. Check your .env file.")

    allowed_exts = app.config.get("ALLOWED_EXTENSIONS", {"png", "jpg", "jpeg", "pdf", "bmp", "tiff", "tif", "webp"})

    def allowed_file(filename: str) -> bool:
        return "." in filename and filename.rsplit(".", 1)[1].lower() in allowed_exts

    @app.get("/")
    def index():
        return jsonify({
            "message": "Simple Invoice OCR API running",
            "endpoints": [
                "/api/health",
                "/api/ocr/process [POST multipart]",
                "/api/ocr/status/<task_id> [GET]",
                "/api/ocr/result/<task_id> [GET]",
                "/api/invoice/extract [POST json]"
            ]
        }), 200

    @app.get("/demo")
    def demo_form():
        # Minimal HTML form for manual testing
        return (
            """
            <!doctype html>
            <html>
            <head><meta charset=\"utf-8\"><title>Simple OCR Demo</title></head>
            <body>
                <h1>Upload file for OCR</h1>
                <form action=\"/api/ocr/process\" method=\"post\" enctype=\"multipart/form-data\">
                    <div><label>File: <input type=\"file\" name=\"file\" required></label></div>
                    <div><label>Language: <input type=\"text\" name=\"language\" value=\"en\"></label></div>
                    <div><label>Use GPU: <input type=\"checkbox\" name=\"use_gpu\" value=\"true\"></label></div>
                    <div><button type=\"submit\">Start OCR</button></div>
                </form>
                <p>After starting, poll <code>/api/ocr/status/&lt;task_id&gt;</code> and get results from <code>/api/ocr/result/&lt;task_id&gt;</code>.</p>
            </body>
            </html>
            """,
            200,
            {"Content-Type": "text/html; charset=utf-8"}
        )

    @app.get("/api/health")
    def health():
        return jsonify({"status": "ok", "mode": "simple", "time": time.time()}), 200

    @app.get("/api/ocr/process")
    def ocr_process_get_info():
        return jsonify({
            "status": "error",
            "message": "Use POST multipart/form-data to /api/ocr/process with key 'file'",
            "example": {
                "method": "POST",
                "url": "/api/ocr/process",
                "form-data": [
                    {"key": "file", "type": "file"},
                    {"key": "language", "value": "en"},
                    {"key": "use_gpu", "value": "false"}
                ]
            }
        }), 405

    @app.post("/api/ocr/process")
    def ocr_process():
        # Debug info for troubleshooting Postman issues
        # (Not logged to console to keep output minimal; returned on validation error instead.)
        # Accept several common field names for file uploads (Postman/browser)
        file_field_candidates = ["file", "pdf", "image", "upload"]
        file = None
        for key in file_field_candidates:
            if key in request.files:
                file = request.files.get(key)
                break
        if not file:
            # Support raw binary uploads (Postman Body: binary). Provide filename via X-Filename header.
            ct = (request.content_type or "").lower()
            if any(x in ct for x in ["application/pdf", "application/octet-stream", "image/"]):
                raw = request.get_data(cache=False, as_text=False)
                if raw:
                    filename = request.headers.get("X-Filename", f"upload_{uuid.uuid4().hex[:8]}")
                    base_name = os.path.splitext(filename)[0] or "upload"
                    safe_base = secure_filename(base_name)
                    ext = os.path.splitext(filename)[1] or ""
                    unique_suffix = f"{int(time.time())}_{uuid.uuid4().hex[:8]}"
                    filename = f"{safe_base}_{unique_suffix}{ext}"
                    upload_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
                    with open(upload_path, "wb") as fh:
                        fh.write(raw)
                    # Proceed to enqueue task using saved upload_path
                    language = (request.args.get("language") or request.form.get("language") or "en").strip() or "en"
                    use_gpu = str(request.args.get("use_gpu") or request.form.get("use_gpu") or "false").lower() in {"1", "true", "yes", "on"}
                    task_id = uuid.uuid4().hex
                    TASKS[task_id] = {
                        "status": "processing",
                        "filename": filename,
                        "created_at": time.time(),
                        "language": language,
                        "use_gpu": use_gpu,
                        "result": None,
                        "error": None,
                    }
                    def worker_bin(path: str, lang: str, use_gpu_flag: bool, tid: str):
                        try:
                            texts = process_ocr(path, app.config["OUTPUT_FOLDER"], lang=lang, use_gpu=use_gpu_flag)
                            TASKS[tid]["result"] = {
                                "detected_texts": texts,
                                "all_text": "\n".join(texts),
                                "pages_processed": len(texts),
                            }
                            TASKS[tid]["status"] = "completed"
                        except Exception as e:
                            TASKS[tid]["status"] = "failed"
                            TASKS[tid]["error"] = str(e)
                    threading.Thread(target=worker_bin, args=(upload_path, language, use_gpu, task_id), daemon=True).start()
                    return jsonify({"task_id": task_id, "status": "processing", "message": "OCR processing started"}), 202

            # Support JSON pointing to an existing file path for quick testing
            payload = request.get_json(silent=True) or {}
            file_path = (payload.get("file_path") or "").strip()
            if file_path and os.path.isfile(file_path):
                language = (payload.get("language") or "en").strip() or "en"
                use_gpu = str(payload.get("use_gpu") or "false").lower() in {"1", "true", "yes", "on"}
                # Copy file into uploads to keep behavior consistent
                base_name = os.path.splitext(os.path.basename(file_path))[0] or "upload"
                safe_base = secure_filename(base_name)
                ext = os.path.splitext(file_path)[1]
                unique_suffix = f"{int(time.time())}_{uuid.uuid4().hex[:8]}"
                filename = f"{safe_base}_{unique_suffix}{ext}"
                upload_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
                try:
                    with open(file_path, "rb") as src, open(upload_path, "wb") as dst:
                        dst.write(src.read())
                except Exception as e:
                    return jsonify({"status": "error", "message": f"failed to read file_path: {e}"}), 400
                task_id = uuid.uuid4().hex
                TASKS[task_id] = {
                    "status": "processing",
                    "filename": filename,
                    "created_at": time.time(),
                    "language": language,
                    "use_gpu": use_gpu,
                    "result": None,
                    "error": None,
                }
                def worker_json(path: str, lang: str, use_gpu_flag: bool, tid: str):
                    try:
                        texts = process_ocr(path, app.config["OUTPUT_FOLDER"], lang=lang, use_gpu=use_gpu_flag)
                        TASKS[tid]["result"] = {
                            "detected_texts": texts,
                            "all_text": "\n".join(texts),
                            "pages_processed": len(texts),
                        }
                        TASKS[tid]["status"] = "completed"
                    except Exception as e:
                        TASKS[tid]["status"] = "failed"
                        TASKS[tid]["error"] = str(e)
                threading.Thread(target=worker_json, args=(upload_path, language, use_gpu, task_id), daemon=True).start()
                return jsonify({"task_id": task_id, "status": "processing", "message": "OCR processing started"}), 202

            return jsonify({
                "status": "error",
                "message": "file is required (use form-data with key 'file') or send raw binary with header 'X-Filename', or JSON with 'file_path'",
                "hint": {
                    "method": request.method,
                    "content_type": request.content_type,
                    "received_file_keys": list(request.files.keys()),
                    "expected_keys": file_field_candidates,
                    "alternatives": {
                        "raw_binary": {
                            "headers": {"X-Filename": "yourfile.pdf"},
                            "query_params": {"language": "en", "use_gpu": "false"}
                        },
                        "json": {"file_path": "F:/path/to/local/file.pdf", "language": "en", "use_gpu": False}
                    }
                }
            }), 400
        if not file or file.filename == "":
            return jsonify({"status": "error", "message": "empty filename"}), 400
        if not allowed_file(file.filename):
            return jsonify({"status": "error", "message": "unsupported file type"}), 400

        language = (request.form.get("language") or request.form.get("lang") or "en").strip() or "en"
        use_gpu = (request.form.get("use_gpu", "false").lower() in {"1", "true", "yes", "on"})

        base_name = os.path.splitext(file.filename)[0] or "upload"
        safe_base = secure_filename(base_name)
        ext = os.path.splitext(file.filename)[1]
        unique_suffix = f"{int(time.time())}_{uuid.uuid4().hex[:8]}"
        filename = f"{safe_base}_{unique_suffix}{ext}"
        upload_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
        file.save(upload_path)

        task_id = uuid.uuid4().hex
        TASKS[task_id] = {
            "status": "processing",
            "filename": filename,
            "created_at": time.time(),
            "language": language,
            "use_gpu": use_gpu,
            "result": None,
            "error": None,
        }

        def worker():
            try:
                texts = process_ocr(upload_path, app.config["OUTPUT_FOLDER"], lang=language, use_gpu=use_gpu)
                result_payload = {
                    "detected_texts": texts,
                    "all_text": "\n".join(texts),
                    "pages_processed": len(texts),
                }
                TASKS[task_id]["result"] = result_payload
                TASKS[task_id]["status"] = "completed"
            except Exception as e:
                TASKS[task_id]["status"] = "failed"
                TASKS[task_id]["error"] = str(e)

        threading.Thread(target=worker, daemon=True).start()
        return jsonify({"task_id": task_id, "status": "processing", "message": "OCR processing started"}), 202

    @app.get("/api/ocr/status/<task_id>")
    def ocr_status(task_id: str):
        data = TASKS.get(task_id)
        if not data:
            return jsonify({"status": "error", "message": "task not found"}), 404
        return jsonify({"task_id": task_id, "status": data.get("status"), "error": data.get("error")}), 200

    @app.get("/api/ocr/result/<task_id>")
    def ocr_result(task_id: str):
        data = TASKS.get(task_id)
        if not data:
            return jsonify({"status": "error", "message": "task not found"}), 404
        if data.get("status") == "processing":
            return jsonify({"task_id": task_id, "status": "processing"}), 202
        if data.get("status") == "failed":
            return jsonify({"status": "error", "message": data.get("error")}), 500
        return jsonify({"task_id": task_id, "status": "completed", "results": data.get("result")}), 200

    @app.post("/api/invoice/extract")
    def invoice_extract():
        payload = request.get_json(force=True, silent=True) or {}
        task_id = (payload.get("task_id") or "").strip()
        if not task_id:
            return jsonify({"status": "error", "message": "task_id is required"}), 400
        data = TASKS.get(task_id)
        if not data:
            return jsonify({"status": "error", "message": "task not found"}), 404
        if data.get("status") != "completed":
            return jsonify({"status": "error", "message": "task not completed"}), 400
        res = data.get("result") or {}
        texts = res.get("detected_texts") or []
        combined = "\n".join(texts)

        # Use Azure LLM for intelligent invoice extraction
        try:
            extracted = extract_structured_from_text(combined)
            # Add success indicator
            extracted["_extraction_method"] = "azure_llm"
            extracted["_extraction_status"] = "success"
        except Exception as e:
            # Fallback to simple regex if Azure fails
            def simple_extract(s: str) -> dict:
                get = lambda p, flags=re.I: (re.search(p, s, flags) or ["", ""]) if isinstance(p, str) else ["", ""]
                def find_first(patterns):
                    for p in patterns:
                        m = re.search(p, s, re.I)
                        if m:
                            return m.group(1).strip()
                    return ""

                invoice_number = find_first([r"Invoice\s*No\.?\s*[:#]?\s*([A-Za-z0-9-_/]+)", r"Invoice\s*#\s*([A-Za-z0-9-_/]+)"])
                invoice_date = find_first([r"Invoice\s*Date\s*[:]?\s*([0-9]{1,2}[\-/][0-9]{1,2}[\-/][0-9]{2,4})", r"Date\s*[:]?\s*([0-9]{1,2}[\-/][0-9]{1,2}[\-/][0-9]{2,4})"])
                total_amount = find_first([r"Total\s*Amount\s*[:$]?\s*([0-9.,]+)", r"Total\s*[:$]?\s*([0-9.,]+)"])
                tax_amount = find_first([r"Tax\s*[:$]?\s*([0-9.,]+)", r"GST\s*[:$]?\s*([0-9.,]+)"])
                vendor_name = find_first([r"Vendor\s*[:]?\s*([A-Za-z0-9 &.,'-]{3,})", r"From\s*[:]?\s*([A-Za-z0-9 &.,'-]{3,})"])
                customer_name = find_first([r"Bill\s*To\s*[:]?\s*([A-Za-z0-9 &.,'-]{3,})", r"Customer\s*[:]?\s*([A-Za-z0-9 &.,'-]{3,})"])

                return {
                    "invoice_number": invoice_number,
                    "invoice_date": invoice_date,
                    "vendor_name": vendor_name,
                    "customer_name": customer_name,
                    "total_amount": total_amount,
                    "tax_amount": tax_amount,
                }

            extracted = simple_extract(combined)
            # Add error info to response
            extracted["_extraction_method"] = "regex_fallback"
            extracted["_azure_error"] = str(e)
        return jsonify({"task_id": task_id, "invoice_data": extracted}), 200

    return app


app = create_app()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5100))
    app.run(host="0.0.0.0", port=port, debug=True)


