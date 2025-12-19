import json
from pathlib import Path

CUSTOMER_FILE = Path("data/customers.json")

def load_customers():
    if CUSTOMER_FILE.exists():
        return json.loads(CUSTOMER_FILE.read_text())
    return {}

def save_customers(customers):
    CUSTOMER_FILE.write_text(
        json.dumps(customers, indent=2)
    )

def normalize_whatsapp(from_field):
    return from_field.replace("whatsapp:+", "").strip()
