import sys
print("🚨🚨🚨 WEBHOOK_APP.PY IS RUNNING 🚨🚨🚨", file=sys.stderr)

import os
import time
import logging
import requests
from pathlib import Path
from flask import Flask, request, jsonify

from utils.customers import normalize_whatsapp
from utils.customer_router import get_sheet_for_customer
from ocr_worker import process_file
from sheets import append_invoice_row

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s"
)

TWILIO_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")

# 🔴 DEFAULT FALLBACK SHEET (TEMPORARY, IMPORTANT)
DEFAULT_SHEET_ID = os.getenv("DEFAULT_SHEET_ID")

if not DEFAULT_SHEET_ID:
    raise RuntimeError("DEFAULT_SHEET_ID env var missing")

app = Flask(__name__)

MEDIA_DIR = Path("data/media")
MEDIA_DIR.mkdir(parents=True, exist_ok=True)

def download_media(media_url: str, dest: Path) -> bool:
    media_url = media_url.rstrip("/") + "/Content"
    logging.info("📎 Trying media: %s", media_url)

    r = requests.get(
        media_url,
        auth=(TWILIO_SID, TWILIO_TOKEN),
        stream=True,
        timeout=30,
    )

    if r.status_code == 404:
        logging.warning("⏳ Media not ready yet — Twilio retry expected")
        return False

    r.raise_for_status()

    with open(dest, "wb") as f:
        for chunk in r.iter_content(16384):
            if chunk:
                f.write(chunk)

    return True

@app.route("/", methods=["GET"])
def home():
    return "OK", 200

@app.route("/webhook/whatsapp", methods=["POST"])
def whatsapp_webhook():
    try:
        media_url = request.form.get("MediaUrl0")
        if not media_url:
            return jsonify({"status": "ignored"}), 200

        from_number = request.form.get("From")
        customer_id = normalize_whatsapp(from_number)

        sheet_id = get_sheet_for_customer(customer_id)

        logging.error("🧪 ROUTED SHEET_ID = %s", sheet_id)

        # 🔴 FORCE FALLBACK
        if not sheet_id:
            logging.error("⚠️ NO CUSTOMER SHEET — USING DEFAULT")
            sheet_id = DEFAULT_SHEET_ID

        msg_id = request.form.get("MessageSid", str(int(time.time())))
        img_path = MEDIA_DIR / f"{msg_id}.jpg"

        ok = download_media(media_url, img_path)
        if not ok:
            return jsonify({"status": "media_not_ready"}), 200

        parsed = process_file(img_path)

        logging.error("🚨 AFTER OCR — GOING TO SHEETS 🚨")
        append_invoice_row(parsed, sheet_id)
        logging.error("✅ SHEETS APPEND COMPLETED")

        return jsonify({"status": "ok"}), 200

    except Exception as e:
        logging.exception("❌ WEBHOOK FAILED")
        return jsonify({"error": str(e)}), 500


