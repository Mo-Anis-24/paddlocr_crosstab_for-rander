import os
import uuid
import time
from flask import Flask, jsonify, request
from flask_cors import CORS
from flask_jwt_extended import jwt_required
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flasgger import Swagger
from werkzeug.utils import secure_filename
from marshmallow import ValidationError

from config import BaseConfig, ensure_directories
from auth import auth_bp, init_jwt
from models import OCRProcessRequestSchema, InvoiceExtractRequestSchema
from ocr_processor import process_ocr
from invoice_extractor import extract_structured_from_text

# Simple task store (Redis recommended; Celery in worker). For now, Redis via rq-like structure
import redis
import json


def create_app() -> Flask:
    app = Flask(__name__)
    app.config.from_object(BaseConfig)
    ensure_directories(BaseConfig)

    # CORS
    CORS(app, resources={r"/api/*": {"origins": app.config.get("CORS_ORIGINS", "*")}})

    # JWT
    init_jwt(app)

    # Rate limiting (uses Redis storage)
    limiter = Limiter(get_remote_address, app=app, storage_uri=app.config.get("RATELIMIT_STORAGE_URL"))

    # Swagger
    Swagger(app)

    # Redis client for task storage
    r = redis.StrictRedis.from_url(app.config.get("REDIS_URL"), decode_responses=True)
    # Celery integration (optional runtime)
    try:
        from .celery_worker import celery_app as celery
    except Exception:
        celery = None

    # Health
    @app.get("/api/v1/health")
    def health():
        return jsonify({"status": "ok"}), 200

    app.register_blueprint(auth_bp)

    def allowed_file(filename: str) -> bool:
        return "." in filename and filename.rsplit(".", 1)[1].lower() in app.config["ALLOWED_EXTENSIONS"]

    @app.post("/api/v1/ocr/process")
    @jwt_required()
    @limiter.limit(lambda: app.config.get("OCR_RATE_LIMIT", "10/minute"))
    def ocr_process():
        # Validate form fields
        schema = OCRProcessRequestSchema()
        try:
            req_args = {k: v for k, v in request.form.items()}
            args = schema.load(req_args)
        except ValidationError as err:
            return jsonify({"status": "error", "message": err.messages}), 400

        if "file" not in request.files:
            return jsonify({"status": "error", "message": "file is required"}), 400
        file = request.files["file"]
        if file.filename == "":
            return jsonify({"status": "error", "message": "empty filename"}), 400
        if not allowed_file(file.filename):
            return jsonify({"status": "error", "message": "unsupported file type"}), 400

        # Save upload
        base_name = os.path.splitext(file.filename)[0] or "upload"
        safe_base = secure_filename(base_name)
        ext = os.path.splitext(file.filename)[1]
        unique_suffix = f"{int(time.time())}_{uuid.uuid4().hex[:8]}"
        filename = f"{safe_base}_{unique_suffix}{ext}"
        upload_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
        file.save(upload_path)

        task_id = uuid.uuid4().hex
        # Store initial status
        r.hset(f"task:{task_id}", mapping={
            "status": "processing",
            "filename": filename,
            "language": args.get("language", "en"),
            "use_gpu": json.dumps(bool(args.get("use_gpu", False)))
        })

        # Background via Celery if available, else thread fallback
        if celery is not None:
            async_res = celery.send_task(
                "tasks.ocr_process",
                args=[upload_path, app.config["OUTPUT_FOLDER"], args.get("language", "en"), bool(args.get("use_gpu", False))],
            )
            r.hset(f"task:{task_id}", "celery_id", async_res.id)
        else:
            import threading

            def worker():
                try:
                    texts = process_ocr(upload_path, app.config["OUTPUT_FOLDER"], lang=args.get("language", "en"), use_gpu=bool(args.get("use_gpu", False)))
                    r.hset(f"task:{task_id}", "status", "completed")
                    r.set(f"task:{task_id}:result", json.dumps({
                        "detected_texts": texts,
                        "all_text": "\n".join(texts),
                        "confidence_scores": [],
                        "processing_time": 0.0
                    }))
                except Exception as e:
                    r.hset(f"task:{task_id}", mapping={"status": "failed", "error": str(e)})

            threading.Thread(target=worker, daemon=True).start()

        return jsonify({"task_id": task_id, "status": "processing", "message": "OCR processing started"}), 202

    @app.get("/api/v1/ocr/status/<task_id>")
    @jwt_required()
    def ocr_status(task_id: str):
        data = r.hgetall(f"task:{task_id}")
        if not data:
            return jsonify({"status": "error", "message": "task not found"}), 404
        # If Celery is used, poll Celery state
        if data.get("status") == "processing" and data.get("celery_id") and celery is not None:
            try:
                async_res = celery.AsyncResult(data.get("celery_id"))
                if async_res.successful():
                    result = async_res.result
                    r.hset(f"task:{task_id}", "status", "completed")
                    r.set(f"task:{task_id}:result", json.dumps(result))
                elif async_res.failed():
                    r.hset(f"task:{task_id}", mapping={"status": "failed", "error": str(async_res.result)})
            except Exception:
                pass
        return jsonify({"task_id": task_id, "status": data.get("status"), "message": data.get("error")}), 200

    @app.get("/api/v1/ocr/result/<task_id>")
    @jwt_required()
    def ocr_result(task_id: str):
        data = r.hgetall(f"task:{task_id}")
        if not data:
            return jsonify({"status": "error", "message": "task not found"}), 404
        result = r.get(f"task:{task_id}:result")
        try:
            results = json.loads(result) if result else None
        except Exception:
            results = None
        return jsonify({"task_id": task_id, "status": data.get("status"), "results": results}), 200

    @app.post("/api/v1/invoice/extract")
    @jwt_required()
    @limiter.limit(lambda: app.config.get("INVOICE_RATE_LIMIT", "5/minute"))
    def invoice_extract():
        schema = InvoiceExtractRequestSchema()
        try:
            payload = schema.load(request.get_json(force=True))
        except ValidationError as err:
            return jsonify({"status": "error", "message": err.messages}), 400
        task_id = payload["task_id"]
        result = r.get(f"task:{task_id}:result")
        if not result:
            return jsonify({"status": "error", "message": "result not found or not ready"}), 404
        try:
            res = json.loads(result)
            texts = res.get("detected_texts") or []
        except Exception:
            return jsonify({"status": "error", "message": "malformed result"}), 500

        # For now, aggregate all pages
        all_text = "\n".join(texts)
        try:
            invoice_data = extract_structured_from_text(all_text)
        except Exception as e:
            return jsonify({"status": "error", "message": str(e)}), 502
        return jsonify({"task_id": task_id, "invoice_data": invoice_data}), 200

    return app


app = create_app()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    app.run(host="0.0.0.0", port=port)


