import os
from dotenv import load_dotenv
from flask import Flask, render_template, request, redirect, url_for, send_from_directory, flash
from werkzeug.utils import secure_filename
import json
import pandas as pd

# ============================
# Azure OpenAI Credentials
# Load from .env file for security
# ============================
# Load environment variables from .env file
load_dotenv()

# Get Azure credentials from environment variables
AZURE_OPENAI_ENDPOINT_CFG = os.environ.get("AZURE_OPENAI_ENDPOINT", "")
AZURE_OPENAI_KEY_CFG = os.environ.get("AZURE_OPENAI_KEY", "")
AZURE_DEPLOYMENT_NAME_CFG = os.environ.get("AZURE_DEPLOYMENT_NAME", "gpt-4o")
# ============================


def convert_to_png(input_path: str, output_dir: str):
	"""Convert an input file (pdf or image) into one or more png files.
	Returns a list of output paths.
	"""
	from typing import List
	paths: List[str] = []
	os.makedirs(output_dir, exist_ok=True)
	base = os.path.splitext(os.path.basename(input_path))[0]
	ext = os.path.splitext(os.path.basename(input_path))[1].lower()

	if ext == ".png":
		return [input_path]

	if ext in {".jpg", ".jpeg", ".bmp", ".tif", ".tiff"}:
		from PIL import Image
		img = Image.open(input_path)
		rgb = img.convert("RGB")
		out_path = os.path.join(output_dir, f"{base}.png")
		rgb.save(out_path, format="PNG")
		return [out_path]

	if ext == ".pdf":
		import pypdfium2 as pdfium
		pdf = pdfium.PdfDocument(input_path)
		for i in range(len(pdf)):
			page = pdf[i]
			bitmap = page.render(scale=2).to_pil()
			out_path = os.path.join(output_dir, f"{base}_page_{i+1}.png")
			bitmap.save(out_path, format="PNG")
			paths.append(out_path)
		return paths

	return []


def create_app() -> Flask:
	# Load .env once at startup so you don't need to export vars in terminal
	try:
		load_dotenv()
	except Exception:
		pass
	app = Flask(__name__)
	app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev-secret")
	app.config["UPLOAD_FOLDER"] = os.path.join(os.getcwd(), "uploads")
	app.config["OUTPUT_FOLDER"] = os.path.join(os.getcwd(), "outputs")
	app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024  # 50 MB

	os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
	os.makedirs(app.config["OUTPUT_FOLDER"], exist_ok=True)

	ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "pdf", "bmp", "tiff", "tif"}

	def is_allowed(filename: str) -> bool:
		return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

	@app.route("/")
	def index():
		return render_template("index.html")

	@app.route("/uploads/<path:filename>")
	def uploaded_file(filename):
		return send_from_directory(app.config["UPLOAD_FOLDER"], filename)

	@app.route("/outputs/<path:filename>")
	def output_file(filename):
		return send_from_directory(app.config["OUTPUT_FOLDER"], filename)

	@app.route("/ocr", methods=["POST"]) 
	def ocr_route():
		file = request.files.get("pdf")
		# Support single or multi-select lang from form; pick first if list
		lang_val = request.form.getlist("lang") or [request.form.get("lang", "en")]
		lang = (lang_val[0] if isinstance(lang_val, list) and lang_val else "en") or "en"
		use_gpu = request.form.get("use_gpu") == "on"
		if file is None:
			flash("No file provided")
			return redirect(url_for("index"))

		orig_name = (file.filename or "").strip()
		# Determine extension
		name_ext = os.path.splitext(orig_name)[1].lower()
		if not name_ext:
			# try mimetype mapping
			mime = (file.mimetype or "").lower()
			mime_map = {
				"application/pdf": ".pdf",
				"image/jpeg": ".jpg",
				"image/jpg": ".jpg",
				"image/png": ".png",
				"image/bmp": ".bmp",
				"image/tiff": ".tiff",
			}
			name_ext = mime_map.get(mime, "")

		if not name_ext:
			flash("No file selected or unknown file type")
			return redirect(url_for("index"))

		if name_ext.lstrip(".") not in ALLOWED_EXTENSIONS:
			flash(f"Unsupported file type: {name_ext}")
			return redirect(url_for("index"))

		# Build a unique, safe filename
		import uuid, time
		base_name = os.path.splitext(orig_name)[0] or "upload"
		safe_base = secure_filename(base_name)
		unique_suffix = f"{int(time.time())}_{uuid.uuid4().hex[:8]}"
		filename = f"{safe_base}_{unique_suffix}{name_ext}"

		upload_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
		file.save(upload_path)

		# Convert to png(s)
		png_paths = convert_to_png(upload_path, app.config["OUTPUT_FOLDER"])  # list of paths
		if not png_paths:
			flash("Conversion failed")
			return redirect(url_for("index"))

		# Run OCR using PaddleOCR
		from paddleocr import PaddleOCR
		from paddleocr import draw_ocr
		import cv2
		import numpy as np

		def _resolve_font_path() -> str:
			# Prefer bundled font if PaddleOCR repo present
			repo_font = os.path.join("PaddleOCR", "doc", "fonts", "latin.ttf")
			if os.path.isfile(repo_font):
				return repo_font
			# Try common Windows fonts
			for f in [
				os.path.join(os.environ.get("WINDIR", r"C:\\Windows"), "Fonts", "arial.ttf"),
				os.path.join(os.environ.get("WINDIR", r"C:\\Windows"), "Fonts", "seguiemj.ttf"),
				os.path.join(os.environ.get("WINDIR", r"C:\\Windows"), "Fonts", "simfang.ttf"),
			]:
				if os.path.isfile(f):
					return f
			# As last resort, try to fetch PaddleOCR fonts (shallow clone)
			try:
				os.system("git clone --depth 1 https://github.com/PaddlePaddle/PaddleOCR 1> NUL 2> NUL")
			except Exception:
				pass
			if os.path.isfile(repo_font):
				return repo_font
			# Fallback: return empty; draw_ocr will still try default but may fail
			return ""

		ocr = PaddleOCR(lang=lang, use_gpu=use_gpu)
		all_text_lines = []
		annotated_previews = []
		num_pages = 0
		per_page_text = []
		for idx, png in enumerate(png_paths):
			num_pages += 1
			result = ocr.ocr(png)
			# Flatten possible nested structure
			if len(result) == 1 and isinstance(result[0], list):
				flat = result[0]
			else:
				flat = result

			# Collect text
			page_lines = []
			for res in flat:
				try:
					text_conf = res[1]
					if isinstance(text_conf, (list, tuple)) and len(text_conf) >= 2:
						text, conf = text_conf[0], text_conf[1]
						conf_val = float(conf[0] if isinstance(conf, (list, tuple)) else conf)
						all_text_lines.append(f"{text}")
						page_lines.append(str(text))
				except Exception:
					pass
			per_page_text.append("\n".join(page_lines))

			# Draw annotated preview image
			boxes = [res[0] for res in flat]
			texts = []
			scores = []
			for res in flat:
				tc = res[1]
				if isinstance(tc, (list, tuple)) and len(tc) >= 2:
					texts.append(str(tc[0]))
					conf = tc[1]
					conf_val = float(conf[0] if isinstance(conf, (list, tuple)) else conf)
					scores.append(conf_val)
				else:
					texts.append(str(tc))
					scores.append(1.0)

			img = cv2.imread(png)
			img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

			# Draw with a guaranteed font path to avoid OSError: cannot open resource
			font_path = _resolve_font_path()
			try:
				if font_path:
					annotated = draw_ocr(img, boxes, texts, scores, font_path=font_path)
				else:
					annotated = draw_ocr(img, boxes, texts, scores)
			except Exception:
				# One more retry without font in case of unexpected font issues
				annotated = draw_ocr(img, boxes, texts, scores)

			annot_bgr = cv2.cvtColor(np.array(annotated), cv2.COLOR_RGB2BGR)
			out_name = f"preview_{idx+1}.png"
			out_path = os.path.join(app.config["OUTPUT_FOLDER"], out_name)
			cv2.imwrite(out_path, annot_bgr)
			annotated_previews.append(out_name)

		# Persist recognized text to a .txt download
		text_content = "\n".join(all_text_lines)
		text_name = os.path.splitext(filename)[0] + ".txt"
		text_path = os.path.join(app.config["OUTPUT_FOLDER"], text_name)
		with open(text_path, "w", encoding="utf-8") as f:
			f.write(text_content)

		# Save per-page JSON for downstream LLM extraction
		json_name = os.path.splitext(filename)[0] + "_pages.json"
		json_path = os.path.join(app.config["OUTPUT_FOLDER"], json_name)
		with open(json_path, "w", encoding="utf-8") as jf:
			json.dump({"pages": per_page_text}, jf, ensure_ascii=False, indent=2)

		return render_template(
			"result.html",
			text=text_content,
			previews=annotated_previews,
			upload_name=filename,
			text_download=text_name,
			num_pages=num_pages,
			num_lines=len(all_text_lines),
			pages_json=os.path.basename(json_path),
		)

	# LLM Excel extraction route (registered within app factory to ensure 'app' exists)
	@app.route("/extract-excel", methods=["POST"])
	def extract_excel():
		# Read pages JSON
		pages_json = request.form.get("pages_json", "")
		if not pages_json:
			flash("Missing pages payload")
			return redirect(url_for("index"))
		json_path = os.path.join(app.config["OUTPUT_FOLDER"], pages_json)
		if not os.path.isfile(json_path):
			flash("Pages file not found")
			return redirect(url_for("index"))

		with open(json_path, "r", encoding="utf-8") as jf:
			data = json.load(jf)
		pages = data.get("pages", [])

		# Use credentials from .env file
		api_key = AZURE_OPENAI_KEY_CFG.strip()
		endpoint = AZURE_OPENAI_ENDPOINT_CFG.strip()
		deployment = AZURE_DEPLOYMENT_NAME_CFG.strip()
		if not api_key or not endpoint or not deployment:
			flash("Azure OpenAI credentials not set. Please check your .env file.")
			return redirect(url_for("index"))

		rows = []
		for idx, page_text in enumerate(pages, start=1):
			fields = call_azure_openai_extract(api_key, endpoint, deployment, page_text)
			fields["page"] = idx
			rows.append(fields)

		df = pd.DataFrame(rows, columns=[
			"page","invoice_number","invoice_date","vendor_name","customer_name","total_amount","tax_amount"
		])

		excel_name = os.path.splitext(os.path.basename(json_path))[0] + "_extracted.xlsx"
		excel_path = os.path.join(app.config["OUTPUT_FOLDER"], excel_name)
		df.to_excel(excel_path, index=False)

		return send_from_directory(app.config["OUTPUT_FOLDER"], excel_name, as_attachment=True)

	return app


def call_azure_openai_extract(api_key: str, endpoint: str, deployment: str, page_text: str) -> dict:
	"""Call Azure OpenAI via REST to extract invoice fields from a page of text.
	Returns keys: invoice_number, invoice_date, vendor_name, customer_name, total_amount, tax_amount.
	"""
	import requests
	api_version = os.environ.get("AZURE_OPENAI_API_VERSION", "2024-08-01-preview")
	url = f"{endpoint.rstrip('/')}/openai/deployments/{deployment}/chat/completions?api-version={api_version}"
	prompt = (
		"You are an information extraction assistant. Given OCR text from an invoice page, "
		"extract the following fields as concise strings. If missing, return empty string. "
		"Fields: Invoice Number, Invoice Date, Vendor Name, Customer Name, Total Amount, Tax Amount.\n\n"
		f"OCR Page Text:\n{page_text}\n\n"
		"Return strict JSON with keys: invoice_number, invoice_date, vendor_name, customer_name, total_amount, tax_amount."
	)
	payload = {
		"messages": [{"role": "user", "content": prompt}],
		"temperature": 0.0,
		"response_format": {"type": "json_object"}
	}
	headers = {"api-key": api_key, "Content-Type": "application/json"}
	try:
		r = requests.post(url, headers=headers, json=payload, timeout=60)
		r.raise_for_status()
		resp = r.json()
		content = resp.get("choices", [{}])[0].get("message", {}).get("content", "{}")
	except Exception:
		content = "{}"
	try:
		data = json.loads(content)
	except Exception:
		start = content.find('{')
		end = content.rfind('}')
		if start != -1 and end != -1 and start < end:
			try:
				data = json.loads(content[start:end+1])
			except Exception:
				data = {}
		else:
			data = {}
	return {
		"invoice_number": str(data.get("invoice_number", "")),
		"invoice_date": str(data.get("invoice_date", "")),
		"vendor_name": str(data.get("vendor_name", "")),
		"customer_name": str(data.get("customer_name", "")),
		"total_amount": str(data.get("total_amount", "")),
		"tax_amount": str(data.get("tax_amount", "")),
	}


 

app = create_app()

if __name__ == "__main__":
	port = int(os.environ.get("PORT", 5000))
	app.run(host="0.0.0.0", port=port, debug=True)