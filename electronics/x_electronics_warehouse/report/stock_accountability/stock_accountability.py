import frappe


def execute(filters=None):
    filters = filters or {}
    conditions = ["sc.docstatus = 1"]
    values = {}
    for field in ["checked_out_to", "warehouse"]:
        if filters.get(field):
            conditions.append(f"sc.{field} = %({field})s")
            values[field] = filters[field]
    if filters.get("only_outstanding"):
        conditions.append("sci.outstanding_qty > 0")

    rows = frappe.db.sql(
        f"""
        SELECT sc.name AS checkout, sc.checkout_date, sc.checked_out_to,
            sc.issued_by, sc.warehouse, sci.item, item.item_code, item.item_name,
            sci.qty, sci.returned_qty, sci.outstanding_qty, sci.rate,
            sci.outstanding_qty * sci.rate AS outstanding_value
        FROM `tabStock Checkout` sc
        INNER JOIN `tabStock Checkout Item` sci ON sci.parent = sc.name
        INNER JOIN `tabItem` item ON item.name = sci.item
        WHERE {" AND ".join(conditions)}
        ORDER BY sc.checkout_date DESC, sc.name DESC
        """,
        values,
        as_dict=True,
    )
    columns = [
        {"label": "Checkout", "fieldname": "checkout", "fieldtype": "Link", "options": "Stock Checkout"},
        {"label": "Date", "fieldname": "checkout_date", "fieldtype": "Date"},
        {"label": "Checked Out To", "fieldname": "checked_out_to", "fieldtype": "Link", "options": "User"},
        {"label": "Issued By", "fieldname": "issued_by", "fieldtype": "Link", "options": "User"},
        {"label": "Warehouse", "fieldname": "warehouse", "fieldtype": "Link", "options": "Warehouse"},
        {"label": "Item", "fieldname": "item_code", "fieldtype": "Data"},
        {"label": "Issued Qty", "fieldname": "qty", "fieldtype": "Float"},
        {"label": "Returned Qty", "fieldname": "returned_qty", "fieldtype": "Float"},
        {"label": "Outstanding Qty", "fieldname": "outstanding_qty", "fieldtype": "Float"},
        {"label": "Outstanding Value", "fieldname": "outstanding_value", "fieldtype": "Currency"},
    ]
    return columns, rows
