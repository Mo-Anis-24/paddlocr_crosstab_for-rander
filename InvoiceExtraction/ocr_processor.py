import os
from typing import List


def convert_to_png(input_path: str, output_dir: str) -> List[str]:
    """Convert an input file (pdf or image) into one or more png files.
    Returns a list of output paths.
    """
    paths: List[str] = []
    os.makedirs(output_dir, exist_ok=True)
    base = os.path.splitext(os.path.basename(input_path))[0]
    ext = os.path.splitext(os.path.basename(input_path))[1].lower()

    if ext == ".png":
        return [input_path]

    if ext in {".jpg", ".jpeg", ".bmp", ".tif", ".tiff", ".webp"}:
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


def run_paddle_ocr(png_paths: List[str], lang: str = "en", use_gpu: bool = False) -> List[str]:
    """Run PaddleOCR for each PNG and return per-page text content."""
    from ocr_utils import create_paddle_ocr

    ocr = create_paddle_ocr(lang=lang, use_gpu=use_gpu)
    per_page_text: List[str] = []
    for png in png_paths:
        result = ocr.ocr(png)
        if len(result) == 1 and isinstance(result[0], list):
            flat = result[0]
        else:
            flat = result
        page_lines = []
        for res in flat:
            try:
                tc = res[1]
                if isinstance(tc, (list, tuple)) and len(tc) >= 2:
                    page_lines.append(str(tc[0]))
                else:
                    page_lines.append(str(tc))
            except Exception:
                pass
        per_page_text.append("\n".join(page_lines))
    return per_page_text


def process_ocr(file_path: str, output_dir: str, lang: str = "en", use_gpu: bool = False) -> List[str]:
    png_paths = convert_to_png(file_path, output_dir)
    if not png_paths:
        return []
    return run_paddle_ocr(png_paths, lang=lang, use_gpu=use_gpu)




