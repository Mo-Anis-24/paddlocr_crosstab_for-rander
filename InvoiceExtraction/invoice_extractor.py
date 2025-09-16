import json
import os
from typing import Dict


def extract_with_azure_openai(api_key: str, endpoint: str, deployment: str, page_text: str, api_version: str) -> Dict[str, str]:
    """Call Azure OpenAI via REST to extract invoice fields from a page of text."""
    import requests

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
        "response_format": {"type": "json_object"},
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
                data = json.loads(content[start:end + 1])
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


def extract_structured_from_text(text_content: str) -> Dict[str, str]:
    api_key = (os.environ.get("AZURE_OPENAI_KEY", "") or "").strip()
    endpoint = (os.environ.get("AZURE_OPENAI_ENDPOINT", "") or "").strip()
    deployment = (os.environ.get("AZURE_DEPLOYMENT_NAME", "gpt-4o") or "").strip()
    api_version = os.environ.get("AZURE_OPENAI_API_VERSION", "2024-08-01-preview")
    if not api_key or not endpoint or not deployment:
        raise ValueError("Azure OpenAI credentials are not configured")
    return extract_with_azure_openai(api_key, endpoint, deployment, text_content, api_version)




