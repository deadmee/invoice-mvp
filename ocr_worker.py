"""
OCR worker for Invoice Automation MVP

Responsibility:
- Take ONE image path
- Run Google Vision OCR
- Parse invoice fields
- Save OCR + parsed JSON
- RETURN parsed data to webhook
"""

import os
import json
import logging
from pathlib import Path

from google.cloud import vision
from google.oauth2 import service_account

from parser import extract_fields

logging.basicConfig(level=logging.INFO)

# ============================================================
# DIRECTORIES
# ============================================================

OCR_DIR = Path("data/ocr")
PARSED_DIR = Path("data/parsed")

OCR_DIR.mkdir(parents=True, exist_ok=True)
PARSED_DIR.mkdir(parents=True, exist_ok=True)

# ============================================================
# GOOGLE VISION CLIENT
# ============================================================

def get_vision_client():
    creds_raw = os.getenv("GOOGLE_APPLICATION_CREDENTIALS_JSON")
    if not creds_raw:
        raise RuntimeError("Missing GOOGLE_APPLICATION_CREDENTIALS_JSON")

    creds_info = json.loads(creds_raw)
    credentials = service_account.Credentials.from_service_account_info(creds_info)
    return vision.ImageAnnotatorClient(credentials=credentials)

# ============================================================
# MAIN FUNCTION (USED BY WEBHOOK ONLY)
# ============================================================

def process_file(image_path: Path) -> dict:
    if not image_path.exists():
        raise FileNotFoundError(image_path)

    logging.info("OCR: Processing %s", image_path.name)

    client = get_vision_client()
    image = vision.Image(content=image_path.read_bytes())
    response = client.text_detection(image=image)

    if response.error.message:
        raise RuntimeError(response.error.message)

    if not response.text_annotations:
        raise RuntimeError("No OCR text detected")

    raw_text = response.text_annotations[0].description

    # Save OCR
    ocr_path = OCR_DIR / f"{image_path.stem}.txt"
    ocr_path.write_text(raw_text, encoding="utf-8")
    logging.info("Wrote OCR -> %s", ocr_path)

    # Parse
    parsed = extract_fields(raw_text)
    parsed["_meta"] = {
        "source_image": image_path.name,
        "ocr_file": ocr_path.name,
    }
    parsed["raw_text"] = raw_text

    # Save parsed JSON
    parsed_path = PARSED_DIR / f"{image_path.stem}.json"
    parsed_path.write_text(
        json.dumps(parsed, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    logging.info("Wrote parsed JSON -> %s", parsed_path)

    return parsed
