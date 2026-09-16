from electronics.x_electronics_warehouse.report.stock_balance.stock_balance import execute as execute_balance


def execute(filters=None):
    filters = filters or {}
    _, balances = execute_balance(
        {
            "to_date": filters.get("to_date"),
            "item": filters.get("item"),
            "warehouse": filters.get("warehouse"),
        }
    )
    rows = [
        row
        for row in balances
        if (row.reorder_level or 0) > 0 and row.qty <= row.reorder_level
    ]

    columns = [
        {"label": "Item Code", "fieldname": "item_code", "fieldtype": "Data"},
        {"label": "Item Name", "fieldname": "item_name", "fieldtype": "Data"},
        {"label": "Warehouse", "fieldname": "warehouse_name", "fieldtype": "Data"},
        {"label": "Batch No", "fieldname": "batch_no", "fieldtype": "Data"},
        {"label": "Serial No", "fieldname": "serial_no", "fieldtype": "Data"},
        {"label": "Quantity", "fieldname": "qty", "fieldtype": "Float"},
        {"label": "Reorder Level", "fieldname": "reorder_level", "fieldtype": "Float"},
        {"label": "Reorder Quantity", "fieldname": "reorder_qty", "fieldtype": "Float"},
        {"label": "Valuation Rate", "fieldname": "rate", "fieldtype": "Currency"},
        {"label": "Stock Value", "fieldname": "value", "fieldtype": "Currency"},
    ]

    return columns, rows
