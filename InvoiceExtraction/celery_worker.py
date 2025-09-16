import os
from celery import Celery


broker_url = os.environ.get("CELERY_BROKER_URL", os.environ.get("REDIS_URL", "redis://redis:6379/0"))
backend_url = os.environ.get("CELERY_RESULT_BACKEND", os.environ.get("REDIS_URL", "redis://redis:6379/0"))

celery_app = Celery("invoice_ocr", broker=broker_url, backend=backend_url)


@celery_app.task(name="tasks.ocr_process")
def ocr_process_task(upload_path: str, output_dir: str, lang: str = "en", use_gpu: bool = False):
    from ocr_processor import process_ocr
    texts = process_ocr(upload_path, output_dir, lang=lang, use_gpu=use_gpu)
    return {
        "detected_texts": texts,
        "all_text": "\n".join(texts),
        "confidence_scores": [],
    }




