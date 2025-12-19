import os
import json
import logging
import random
import re
import time

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

# ============================================================
# GOOGLE SHEETS CONFIG (RENDER SAFE)
# ============================================================

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

CREDS_RAW = os.getenv("GOOGLE_APPLICATION_CREDENTIALS_JSON")
if not CREDS_RAW:
    raise RuntimeError(
        "GOOGLE_APPLICATION_CREDENTIALS_JSON is missing. "
        "Paste FULL service account JSON in Render env vars."
    )

try:
    CREDS_INFO = json.loads(CREDS_RAW)
except Exception as e:
    raise RuntimeError("Invalid JSON in GOOGLE_APPLICATION_CREDENTIALS_JSON") from e

DEFAULT_RANGE = os.getenv("SHEET_RANGE", "Sheet1!A:F")

# ============================================================
# GOOGLE SHEETS SERVICE (SINGLETON)
# ============================================================

_SHEETS_SERVICE = None

def _get_service():
    global _SHEETS_SERVICE
    if _SHEETS_SERVICE is None:
        creds = Credentials.from_service_account_info(
            CREDS_INFO, scopes=SCOPES
        )
        _SHEETS_SERVICE = build(
            "sheets",
            "v4",
            credentials=creds,
            cache_discovery=False
        )
    return _SHEETS_SERVICE

# ============================================================
# HELPERS
# ============================================================

def _normalize_total(val):
    if val is None:
        return ""
    s = str(val).strip()
    s = s.replace(",", "").replace("₹", "").replace("Rs.", "").replace("Rs", "").strip()
    try:
        return f"{float(s):.2f}"
    except Exception:
        return s

# ============================================================
# MAIN APPEND FUNCTION (FORCE APPEND)
# ============================================================

def append_invoice_row(
    parsed: dict,
    sheet_id: str,
    retry: int = 3,
    sheet_range: str = None,
) -> bool:
    """
    Force append invoice data to a CUSTOMER-SPECIFIC Google Sheet.
    No dedupe. No silent skipping.
    """

    if not sheet_id:
        raise ValueError("sheet_id is required")

    logging.info("📤 Google Sheets append STARTED")

    svc = _get_service()
    use_range = sheet_range or DEFAULT_RANGE

    # Build row
    invoice_no = str(parsed.get("invoice_number") or "").strip()
    date = parsed.get("date") or ""
    vendor = (
        parsed.get("vendor")
        or parsed.get("supplier")
        or parsed.get("seller")
        or ""
    )
    total = _normalize_total(
        parsed.get("total")
        or parsed.get("grand_total")
        or parsed.get("amount")
        or ""
    )
    currency = parsed.get("currency") or ""
    raw_snip = (parsed.get("raw_text") or "")[:500]

    row = [invoice_no, date, vendor, total, currency, raw_snip]
    body = {"values": [row]}

    attempt = 0
    while True:
        attempt += 1
        try:
            svc.spreadsheets().values().append(
                spreadsheetId=sheet_id,
                range=use_range,
                valueInputOption="RAW",
                insertDataOption="INSERT_ROWS",
                body=body,
            ).execute()

            logging.info(
                "✅ Google Sheets append SUCCESS (invoice=%s, sheet=%s)",
                invoice_no,
                sheet_id
            )
            return True

        except Exception:
            logging.exception("❌ Sheets append failed (attempt %d)", attempt)
            if attempt >= retry:
                raise
            time.sleep((2 ** attempt) + random.random())
