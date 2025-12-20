import os
import time
import logging
import requests
from pathlib import Path
from flask import Flask, request, jsonify

# ============================================================
# LOGGING (SAFE AT IMPORT TIME)
# ============================================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s"
)

# ============================================================
# FLASK APP (MUST BE FIRST, NO ENV CHECKS HERE)
# ============================================================
app = Flask(__name__)

# ============================================================
# PATHS
# ============================================================
MEDIA_DIR = Path("data/media")
MEDIA_DIR.mkdir(parents=True, exist_ok=True)

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
        # ENV (READ INSIDE FUNCTION — SAFE)
        # ----------------------------------------------------
        TWILIO_SID = os.getenv("TWILIO_ACCOUNT_SID")
        TWILIO_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
        DEFAULT_SHEET_ID = os.getenv("DEFAULT_SHEET_ID")

        if not TWILIO_SID or not TWILIO_TOKEN:
            return jsonify({"error": "Twilio env vars missing"}), 500

        if not DEFAULT_SHEET_ID:
            return jsonify({"error": "DEFAULT_SHEET_ID missing"}), 500

        # ----------------------------------------------------
        # MEDIA
        # ----------------------------------------------------
        media_url = request.form.get("MediaUrl0")
        if not media_url:
            logging.info("No media — ignored")
            return jsonify({"status": "ignored"}), 200

        from_number = request.form.get("From", "unknown")
        msg_id = request.form.get("MessageSid", str(int(time.time())))
        img_path = MEDIA_DIR / f"{msg_id}.jpg"

        # Twilio media needs /Content
        media_url = media_url.rstrip("/") + "/Content"
        logging.info("Downloading media: %s", media_url)

        r = requests.get(
            media_url,
            auth=(TWILIO_SID, TWILIO_TOKEN),
            stream=True,
            timeout=30,
        )

        if r.status_code == 404:
            logging.warning("Media not ready yet")
            return jsonify({"status": "retry"}), 200

        r.raise_for_status()

        with open(img_path, "wb") as f:
            for chunk in r.iter_content(16384):
                if chunk:
                    f.write(chunk)

        logging.info("Media saved: %s", img_path)

        # ----------------------------------------------------
        # OCR
        # ----------------------------------------------------
        from ocr_worker import process_file
        parsed = process_file(img_path)

        logging.info("OCR done, moving to Sheets")

        # ----------------------------------------------------
        # GOOGLE SHEETS (FORCED)
        # ----------------------------------------------------
        from sheets import append_invoice_row
        append_invoice_row(parsed, DEFAULT_SHEET_ID)

        logging.info("Sheets append SUCCESS")

        return jsonify({"status": "ok"}), 200

    except Exception as e:
        logging.exception("WEBHOOK FAILED")
        return jsonify({"error": str(e)}), 500


# ============================================================
# LOCAL RUN (IGNORED BY RENDER)
# ============================================================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
