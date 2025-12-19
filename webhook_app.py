print("🔥🔥🔥 NEW WEBHOOK VERSION LOADED 🔥🔥🔥")
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

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

# ============================================================
# ENV VARS (Render safe)
# ============================================================

TWILIO_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")

if not TWILIO_SID or not TWILIO_TOKEN:
    raise RuntimeError("Missing Twilio credentials")

# ============================================================
# APP
# ============================================================

app = Flask(__name__)

# ============================================================
# DIRECTORIES
# ============================================================

MEDIA_DIR = Path("data/media")
MEDIA_DIR.mkdir(parents=True, exist_ok=True)

# ============================================================
# HELPERS
# ============================================================

def download_media(media_url: str, dest: Path):
    logging.info("⬇️ Downloading media")
    r = requests.get(
        media_url,
        auth=(TWILIO_SID, TWILIO_TOKEN),
        stream=True,
        timeout=30
    )
    r.raise_for_status()
    with open(dest, "wb") as f:
        for chunk in r.iter_content(1024 * 16):
            if chunk:
                f.write(chunk)

# ============================================================
# ROUTES
# ============================================================

@app.route("/", methods=["GET"])
def home():
    return "Webhook running", 200


@app.route("/webhook/whatsapp", methods=["POST"])
def whatsapp_webhook():
    """
    MAIN WhatsApp webhook
    """

    try:
        # -----------------------------
        # 1️⃣ Identify customer
        # -----------------------------
        from_number = request.form.get("From")
        if not from_number:
            return jsonify({"error": "Missing From"}), 400

        customer_id = normalize_whatsapp(from_number)
        logging.info("🧭 Customer identified: %s", customer_id)

        sheet_id = get_sheet_for_customer(customer_id)
        logging.info("📄 Sheet resolved: %s", sheet_id)

        # -----------------------------
        # 2️⃣ Media check
        # -----------------------------
        num_media = int(request.form.get("NumMedia", "0"))
        if num_media == 0:
            logging.info("No media sent")
            return jsonify({"status": "no_media"}), 200

        media_url = request.form.get("MediaUrl0")
        if not media_url:
            return jsonify({"error": "Missing MediaUrl0"}), 400

        message_id = request.form.get("MessageSid", str(int(time.time())))
        img_path = MEDIA_DIR / f"{message_id}.jpg"

        # -----------------------------
        # 3️⃣ Download invoice
        # -----------------------------
        download_media(media_url, img_path)

        # -----------------------------
        # 4️⃣ OCR + Parse
        # -----------------------------
        parsed_data = process_file(img_path)
        logging.info("🧪 Parsed data keys: %s", list(parsed_data.keys()))

        # -----------------------------
        # 5️⃣ Append to Google Sheets
        # -----------------------------
        append_invoice_row(parsed_data, sheet_id)

        logging.info("✅ Invoice stored successfully")

        return jsonify({"status": "ok"}), 200

    except Exception as e:
        logging.exception("❌ Webhook failed")
        return jsonify({"status": "error", "error": str(e)}), 500


# ============================================================
# LOCAL DEV ONLY
# ============================================================

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
