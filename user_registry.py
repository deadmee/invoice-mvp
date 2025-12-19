import os
import json
import logging

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

logging.basicConfig(level=logging.INFO)

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

# 🔥 USER REGISTRY SHEET ID (ONE TIME)
USER_REGISTRY_SHEET_ID = "PASTE_USER_REGISTRY_SHEET_ID"

# Expect columns:
# A = whatsapp_number
# B = sheet_id
USER_REGISTRY_RANGE = "Sheet1!A:B"


def _get_service():
    creds_raw = os.getenv("GOOGLE_APPLICATION_CREDENTIALS_JSON")
    creds_info = json.loads(creds_raw)
    creds = Credentials.from_service_account_info(creds_info, scopes=SCOPES)
    return build("sheets", "v4", credentials=creds, cache_discovery=False)


def get_sheet_id_for_user(from_number: str) -> str | None:
    """
    Lookup Google Sheet ID for a WhatsApp sender.
    Returns None if user not registered.
    """
    svc = _get_service()
    res = svc.spreadsheets().values().get(
        spreadsheetId=USER_REGISTRY_SHEET_ID,
        range=USER_REGISTRY_RANGE
    ).execute()

    rows = res.get("values", [])

    for row in rows:
        if len(row) < 2:
            continue
        if row[0].strip() == from_number:
            logging.info("📘 Found sheet for %s", from_number)
            return row[1].strip()

    logging.warning("❌ No sheet registered for %s", from_number)
    return None
