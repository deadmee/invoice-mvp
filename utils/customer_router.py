from datetime import datetime
from utils.customers import load_customers, save_customers
from utils.sheets_manager import create_customer_sheet

def get_sheet_for_customer(customer_id):
    customers = load_customers()

    if customer_id not in customers:
        sheet_id = create_customer_sheet(customer_id)
        customers[customer_id] = {
            "sheet_id": sheet_id,
            "created_at": datetime.utcnow().isoformat()
        }
        save_customers(customers)

    return customers[customer_id]["sheet_id"]
