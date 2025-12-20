print("🔥 FINAL WEBHOOK LOADED — MEDIAURL0 ONLY 🔥")

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

# ============================================================
# LOGGING
# ============================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s"
)

# ============================================================
# ENV
# ============================================================

TWILIO_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")

if not TWILIO_SID or not TWILIO_TOKEN:
    raise RuntimeError("Missing Twilio credentials")

# ============================================================
# APP
# ============================================================

app = Flask(__name__)

MEDIA_DIR = Path("data/media")
MEDIA_DIR.mkdir(parents=True, exist_ok=True)

# ============================================================
# MEDIA DOWNLOAD — ONLY MediaUrl0
# ============================================================

def download_media(media_url: str, dest: Path):
    logging.error("📎 USING MediaUrl0 EXACTLY: %s", media_url)

    if not media_url.startswith("https://"):
        raise RuntimeError(f"Invalid MediaUrl0: {media_url}")

    r = requests.get(
        media_url,
        auth=(TWILIO_SID, TWILIO_TOKEN),
        stream=True,
        timeout=30,
    )

    r.raise_for_status()

    with open(dest, "wb") as f:
        for chunk in r.iter_content(16384):
            if chunk:
                f.write(chunk)

    logging.info("📥 Media saved to %s", dest)

# ============================================================
# ROUTES
# ============================================================

@app.route("/", methods=["GET"])
def home():
    return "OK", 200


@app.route("/webhook/whatsapp", methods=["POST"])
def whatsapp_webhook():
    try:
        # ----------------------------------------------------
        # 1️⃣ ONLY HANDLE REAL MEDIA CALLBACK
        # ----------------------------------------------------
        media_url = request.form.get("MediaUrl0")
        if not media_url:
            logging.info("Ignoring callback without MediaUrl0")
            return jsonify({"status": "ignored"}), 200

        # ----------------------------------------------------
        # 2️⃣ CUSTOMER
        # ----------------------------------------------------
        from_number = request.form.get("From")
        if not from_number:
            raise RuntimeError("Missing From number")

        customer_id = normalize_whatsapp(from_number)
        logging.info("🧭 Customer identified: %s", customer_id)

        sheet_id = get_sheet_for_customer(customer_id)
        logging.info("📄 Sheet resolved: %s", sheet_id)

        # ----------------------------------------------------
        # 3️⃣ FILE PATH
        # ----------------------------------------------------
        msg_id = request.form.get("MessageSid", str(int(time.time())))
        img_path = MEDIA_DIR / f"{msg_id}.jpg"

        # ----------------------------------------------------
        # 4️⃣ DOWNLOAD MEDIA (NO URL BUILDING)
        # ----------------------------------------------------
        download_media(media_url, img_path)

        # ----------------------------------------------------
        # 5️⃣ OCR (PURE)
        # ----------------------------------------------------
        parsed_data = process_file(img_path)
        logging.error("🚨 AFTER OCR — GOING TO SHEETS 🚨")

        # ----------------------------------------------------
        # 6️⃣ GOOGLE SHEETS
        # ----------------------------------------------------
        append_invoice_row(parsed_data, sheet_id)
        logging.info("✅ GOOGLE SHEETS APPEND SUCCESS")

        return jsonify({"status": "ok"}), 200

    except Exception as e:
        logging.exception("❌ WEBHOOK FAILED")
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
