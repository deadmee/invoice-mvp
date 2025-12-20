import os
import json
import logging
import time
import random
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

logging.basicConfig(level=logging.INFO)

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

CREDS = json.loads(os.getenv("GOOGLE_APPLICATION_CREDENTIALS_JSON"))

SERVICE = None

def get_service():
    global SERVICE
    if SERVICE is None:
        creds = Credentials.from_service_account_info(CREDS, scopes=SCOPES)
        SERVICE = build("sheets", "v4", credentials=creds, cache_discovery=False)
    return SERVICE

def append_invoice_row(parsed: dict, sheet_id: str, retries=3):
    service = get_service()

    row = [
        parsed.get("invoice_number", ""),
        parsed.get("date", ""),
        parsed.get("supplier", ""),
        parsed.get("total", ""),
        parsed.get("raw_text", "")[:500],
    ]

    body = {"values": [row]}

    for attempt in range(1, retries + 1):
        try:
            service.spreadsheets().values().append(
                spreadsheetId=sheet_id,
                range="Sheet1!A:E",
                valueInputOption="RAW",
                insertDataOption="INSERT_ROWS",
                body=body,
            ).execute()

            logging.info("✅ SHEET APPEND SUCCESS")
            return

        except Exception:
            logging.exception("❌ Sheets append failed (%d)", attempt)
            time.sleep(2 ** attempt + random.random())

    raise RuntimeError("Sheets append failed")

