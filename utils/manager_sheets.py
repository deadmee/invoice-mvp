import gspread
from google.oauth2.service_account import Credentials

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
CREDS_FILE = "service_account.json"  # same one you already use

def create_customer_sheet(customer_id):
    creds = Credentials.from_service_account_file(
        CREDS_FILE, scopes=SCOPES
    )
    gc = gspread.authorize(creds)

    sheet = gc.create(f"Invoice_Data_{customer_id}")
    ws = sheet.sheet1

    headers = [
        "Invoice Number",
        "Invoice Date",
        "Vendor Name",
        "Subtotal",
        "Tax",
        "Total",
        "Source File"
    ]

    ws.append_row(headers)
    return sheet.id
