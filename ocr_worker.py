"""
OCR worker for Invoice Automation MVP (Google Cloud Vision).
Scalable multi-user version:
WhatsApp sender → User Registry Sheet → User-specific Google Sheet.
"""

import os
import json
import logging
import io
import time
from pathlib import Path

from pdf2image import convert_from_path
from google.cloud import vision

from sheets import append_invoice_row
from user_registry import get_sheet_id_for_user

# -------------------------------------------------
# LOGGING
# -------------------------------------------------
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

# -------------------------------------------------
# GOOGLE VISION CLIENT
# -------------------------------------------------
def get_vision_client():
    creds_raw = os.getenv("GOOGLE_APPLICATION_CREDENTIALS_JSON")
    if not creds_raw:
        raise RuntimeError("GOOGLE_APPLICATION_CREDENTIALS_JSON missing")

    creds_info = json.loads(creds_raw)
    logging.info("🔥 USING VISION PROJECT ID: %s", creds_info.get("project_id"))

    return vision.ImageAnnotatorClient.from_service_account_info(creds_info)

# -------------------------------------------------
# OPTIONAL PARSER
# -------------------------------------------------
try:
    from parser import extract_fields
except Exception:
    extract_fields = None

# -------------------------------------------------
# PATHS
# -------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent
MEDIA_DIR = BASE_DIR / "data" / "media"
OCR_DIR = BASE_DIR / "data" / "ocr"
PARSED_DIR = BASE_DIR / "data" / "parsed"
PROCESSED_MEDIA_DIR = MEDIA_DIR / "processed"

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp"}
PDF_EXTS = {".pdf"}

for d in [MEDIA_DIR, OCR_DIR, PARSED_DIR, PROCESSED_MEDIA_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# -------------------------------------------------
# HELPERS
# -------------------------------------------------
def is_processed(path: Path) -> bool:
    return (OCR_DIR / f"{path.stem}.txt").exists()

def write_text(path: Path, text: str):
    out = OCR_DIR / f"{path.stem}.txt"
    out.write_text(text, encoding="utf-8")
    logging.info("Wrote OCR -> %s", out)

def write_parsed(path: Path, data: dict):
    out = PARSED_DIR / f"{path.stem}.json"
    out.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    logging.info("Wrote parsed JSON -> %s", out)

def move_processed(path: Path):
    dest = PROCESSED_MEDIA_DIR / path.name
    path.rename(dest)
    logging.info("Moved processed media -> %s", dest)

def normalize_money(x):
    if not x:
        return ""
    try:
        return f"{float(str(x).replace(',', '').replace('₹', '')):.2f}"
    except Exception:
        return str(x)

# -------------------------------------------------
# OCR FUNCTIONS
# -------------------------------------------------
def ocr_image(path: Path) -> str:
    client = get_vision_client()
    image = vision.Image(content=path.read_bytes())
    response = client.text_detection(image=image)

    if response.error.message:
        logging.error("Vision error: %s", response.error.message)
        return ""

    return response.text_annotations[0].description if response.text_annotations else ""

def ocr_pdf(path: Path) -> str:
    client = get_vision_client()
    text_blocks = []

    pages = convert_from_path(str(path), dpi=200)
    for page in pages:
        buf = io.BytesIO()
        page.save(buf, format="JPEG")
        image = vision.Image(content=buf.getvalue())
        response = client.text_detection(image=image)

        if response.text_annotations:
            text_blocks.append(response.text_annotations[0].description)

    return "\n".join(text_blocks)

# -------------------------------------------------
# MAIN PIPELINE
# -------------------------------------------------
def process_file(path: Path, from_number: str):
    if is_processed(path):
        logging.info("Already processed %s", path.name)
        return

    logging.info("Processing %s (from %s)", path.name, from_number)

    if path.suffix.lower() in IMAGE_EXTS:
        text = ocr_image(path)
    elif path.suffix.lower() in PDF_EXTS:
        text = ocr_pdf(path)
    else:
        logging.warning("Unsupported file %s", path.name)
        return

    write_text(path, text)

    parsed = {
        "file": path.name,
        "raw_text": text,
        "from_number": from_number,
    }

    if extract_fields:
        try:
            fields = extract_fields(text)
            parsed.update({
                "invoice_number": fields.get("invoice_number"),
                "date": fields.get("date"),
                "supplier": fields.get("supplier"),
                "total": normalize_money(fields.get("total")),
            })
        except Exception:
            logging.exception("Parser failed")

    write_parsed(path, parsed)

    # -------------------------------------------------
    # DYNAMIC SHEET ROUTING (THOUSANDS OF USERS)
    # -------------------------------------------------
    sheet_id = get_sheet_id_for_user(from_number)

    if not sheet_id:
        logging.warning("❌ User %s not registered — skipping Sheets append", from_number)
    else:
        try:
            logging.info("📤 Appending invoice for %s to sheet %s", from_number, sheet_id)
            append_invoice_row(parsed, sheet_id)
            logging.info("✅ Sheets append SUCCESS")
        except Exception:
            logging.exception("❌ Sheets append FAILED")

    move_processed(path)

# -------------------------------------------------
# ENTRY POINT (CALLED FROM WEBHOOK)
# -------------------------------------------------
def run_ocr_for_sender(from_number: str):
    for f in MEDIA_DIR.glob("*"):
        if f.is_file():
            process_file(f, from_number)
            time.sleep(0.1)
