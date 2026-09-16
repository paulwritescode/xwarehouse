import frappe


def execute(filters=None):
    filters = filters or {}
    conditions = ["sle.posting_date <= %(to_date)s"]
    values = {"to_date": filters.get("to_date") or frappe.utils.today()}

    for field in ["item", "warehouse"]:
        if filters.get(field):
            conditions.append(f"sle.{field} = %({field})s")
            values[field] = filters[field]

    rows = frappe.db.sql(
        f"""
        SELECT
            sle.item,
            item.item_code,
            item.item_name,
            item.tracking_method,
            item.reorder_level,
            item.reorder_qty,
            sle.warehouse,
            warehouse.warehouse_name,
            sle.batch_no,
            sle.serial_no,
            sle.qty_after_transaction AS qty,
            sle.valuation_rate AS rate,
            sle.stock_value AS value,
            sle.posting_date,
            sle.posting_time,
            sle.creation
        FROM `tabStock Ledger Entry` sle
        INNER JOIN `tabItem` item ON item.name = sle.item
        INNER JOIN `tabWarehouse` warehouse ON warehouse.name = sle.warehouse
        WHERE {" AND ".join(conditions)}
        ORDER BY
            sle.item,
            sle.warehouse,
            sle.posting_date DESC,
            sle.posting_time DESC,
            sle.creation DESC
        """,
        values,
        as_dict=True,
    )

    latest = {}
    for row in rows:
        if row.tracking_method == "Batch":
            identifier = row.batch_no or ""
        elif row.tracking_method == "Serial":
            identifier = row.serial_no or ""
        else:
            identifier = None

        key = (row.item, row.warehouse, identifier)
        if key not in latest:
            latest[key] = row

    result = sorted(
        latest.values(),
        key=lambda row: (row.item_code, row.warehouse_name, row.batch_no or "", row.serial_no or ""),
    )

    columns = [
        {"label": "Item Code", "fieldname": "item_code", "fieldtype": "Data"},
        {"label": "Item Name", "fieldname": "item_name", "fieldtype": "Data"},
        {"label": "Warehouse", "fieldname": "warehouse_name", "fieldtype": "Data"},
        {"label": "Batch No", "fieldname": "batch_no", "fieldtype": "Data"},
        {"label": "Serial No", "fieldname": "serial_no", "fieldtype": "Data"},
        {"label": "Quantity In Stock", "fieldname": "qty", "fieldtype": "Float"},
        {"label": "Moving Average Rate", "fieldname": "rate", "fieldtype": "Currency"},
        {"label": "Stock Value", "fieldname": "value", "fieldtype": "Currency"},
    ]

    return columns, result
