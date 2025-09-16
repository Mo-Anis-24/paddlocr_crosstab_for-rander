import os


def create_paddle_ocr(lang: str = "en", use_gpu: bool = False):

	from paddleocr import PaddleOCR

	use_local = (os.environ.get("OCR_USE_LOCAL_MODELS", "") or "").strip().lower() in {"1", "true", "yes", "on"}
	det_dir = (os.environ.get("OCR_DET_MODEL_DIR", "") or "").strip()
	rec_dir = (os.environ.get("OCR_REC_MODEL_DIR", "") or "").strip()
	cls_dir = (os.environ.get("OCR_CLS_MODEL_DIR", "") or "").strip()

	kwargs = {
		"lang": lang,
		"use_gpu": use_gpu,
		"show_log": False,
	}

	if use_local or det_dir or rec_dir or cls_dir:
		if det_dir:
			kwargs["det_model_dir"] = det_dir
		if rec_dir:
			kwargs["rec_model_dir"] = rec_dir
		if cls_dir:
			kwargs["cls_model_dir"] = cls_dir
			kwargs["use_angle_cls"] = True

		for key in ("det_model_dir", "rec_model_dir", "cls_model_dir"):
			if key in kwargs and not os.path.isdir(kwargs[key]):
				raise FileNotFoundError(f"{key} not found at {kwargs[key]}. Set correct path or unset OCR_USE_LOCAL_MODELS.")

		return PaddleOCR(**kwargs)

	if (os.environ.get("OCR_DISABLE_DOWNLOAD", "") or "").strip().lower() in {"1", "true", "yes", "on"}:
		raise RuntimeError(
			"PaddleOCR model download is disabled and no local model dirs provided. "
			"Set OCR_DET_MODEL_DIR / OCR_REC_MODEL_DIR (/ OCR_CLS_MODEL_DIR) or enable downloads."
		)

	return PaddleOCR(**kwargs)



