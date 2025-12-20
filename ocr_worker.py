"""
PURE OCR WORKER
NO Twilio
NO Sheets
"""

import os
import json
import logging
from pathlib import Path
from google.cloud import vision
from google.oauth2 import service_account
from parser import extract_fields

logging.basicConfig(level=logging.INFO)

OCR_DIR = Path("data/ocr")
PARSED_DIR = Path("data/parsed")
PROCESSED_DIR = Path("data/media/processed")

for d in [OCR_DIR, PARSED_DIR, PROCESSED_DIR]:
    d.mkdir(parents=True, exist_ok=True)

def get_vision_client():
    creds = json.loads(os.getenv("GOOGLE_APPLICATION_CREDENTIALS_JSON"))
    credentials = service_account.Credentials.from_service_account_info(creds)
    logging.info("🔥 USING VISION PROJECT ID: %s", creds.get("project_id"))
    return vision.ImageAnnotatorClient(credentials=credentials)

def process_file(image_path: Path) -> dict:
    logging.info("Processing %s", image_path.name)

    client = get_vision_client()
    image = vision.Image(content=image_path.read_bytes())
    response = client.text_detection(image=image)

    if not response.text_annotations:
        raise RuntimeError("No OCR text detected")

    raw_text = response.text_annotations[0].description

    (OCR_DIR / f"{image_path.stem}.txt").write_text(raw_text, encoding="utf-8")

    parsed = extract_fields(raw_text)
    parsed["raw_text"] = raw_text

    (PARSED_DIR / f"{image_path.stem}.json").write_text(
        json.dumps(parsed, indent=2), encoding="utf-8"
    )

    image_path.rename(PROCESSED_DIR / image_path.name)

    return parsed
