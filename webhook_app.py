import sys
print("🚨 WEBHOOK_APP.PY LOADED 🚨", file=sys.stderr)

import os
import time
import logging
import requests
from pathlib import Path
from flask import Flask, request, jsonify

from ocr_worker import process_file
from sheets import append_invoice_row

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

# ================= ENV =================

TWILIO_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
DEFAULT_SHEET_ID = os.getenv("DEFAULT_SHEET_ID")

if not TWILIO_SID or not TWILIO_TOKEN:
    raise RuntimeError("Twilio credentials missing")

if not DEFAULT_SHEET_ID:
    raise RuntimeError("DEFAULT_SHEET_ID missing")

# ================= APP =================

app = Flask(__name__)

MEDIA_DIR = Path("data/media")
MEDIA_DIR.mkdir(parents=True, exist_ok=True)

# ================= TWILIO MEDIA =================

def download_media(media_url: str, dest: Path, retries=6, delay=2):
    media_url = media_url.rstrip("/") + "/Content"
    logging.info("📎 Fetching media: %s", media_url)

    for attempt in range(1, retries + 1):
        r = requests.get(
            media_url,
            auth=(TWILIO_SID, TWILIO_TOKEN),
            stream=True,
            timeout=30,
        )

        if r.status_code == 404:
            logging.warning("⏳ Media not ready (%d/%d)", attempt, retries)
            time.sleep(delay)
            continue

        r.raise_for_status()

        with open(dest, "wb") as f:
            for chunk in r.iter_content(16384):
                if chunk:
                    f.write(chunk)

        logging.info("📥 Media downloaded")
        return True

    logging.warning("❌ Media never became available")
    return False

# ================= ROUTES =================

@app.route("/", methods=["GET"])
def home():
    return "OK", 200


@app.route("/webhook/whatsapp", methods=["POST"])
def whatsapp_webhook():
    media_url = request.form.get("MediaUrl0")
    if not media_url:
        return jsonify({"status": "ignored"}), 200

    msg_id = request.form.get("MessageSid", str(int(time.time())))
    img_path = MEDIA_DIR / f"{msg_id}.jpg"

    ok = download_media(media_url, img_path)
    if not ok:
        # IMPORTANT: return 200 so Twilio retries
        return jsonify({"status": "waiting"}), 200

    parsed = process_file(img_path)

    logging.error("🚨 AFTER OCR — APPENDING TO SHEETS 🚨")
    append_invoice_row(parsed, DEFAULT_SHEET_ID)
    logging.error("✅ GOOGLE SHEETS APPEND DONE")

    return jsonify({"status": "ok"}), 200
