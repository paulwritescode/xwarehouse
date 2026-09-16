import frappe


def execute(filters=None):
    filters = filters or {}
    conditions = ["sc.docstatus = 1"]
    values = {}
    for field in ["warehouse", "counted_by"]:
        if filters.get(field):
            conditions.append(f"sc.{field} = %({field})s")
            values[field] = filters[field]
    # This report is intentionally discrepancy-only. Clean stock counts never appear here.
    conditions.append("sci.variance != 0")
    rows = frappe.db.sql(
        f"""
        SELECT sc.name AS stock_count, sc.count_date, sc.warehouse, sc.counted_by,
            sci.item, item.item_code, item.item_name, sci.system_qty, sci.counted_qty,
            sci.variance, sci.variance_value, sc.adjustment_stock_entry
        FROM `tabStock Count` sc
        INNER JOIN `tabStock Count Item` sci ON sci.parent = sc.name
        INNER JOIN `tabItem` item ON item.name = sci.item
        WHERE {" AND ".join(conditions)}
        ORDER BY sc.count_date DESC, sc.name DESC
        """,
        values,
        as_dict=True,
    )
    columns = [
        {"label": "Stock Count", "fieldname": "stock_count", "fieldtype": "Link", "options": "Stock Count"},
        {"label": "Date", "fieldname": "count_date", "fieldtype": "Date"},
        {"label": "Warehouse", "fieldname": "warehouse", "fieldtype": "Link", "options": "Warehouse"},
        {"label": "Counted By", "fieldname": "counted_by", "fieldtype": "Link", "options": "User"},
        {"label": "Item", "fieldname": "item_code", "fieldtype": "Data"},
        {"label": "System Qty", "fieldname": "system_qty", "fieldtype": "Float"},
        {"label": "Counted Qty", "fieldname": "counted_qty", "fieldtype": "Float"},
        {"label": "Variance", "fieldname": "variance", "fieldtype": "Float"},
        {"label": "Variance Value", "fieldname": "variance_value", "fieldtype": "Currency"},
        {"label": "Adjustment", "fieldname": "adjustment_stock_entry", "fieldtype": "Link", "options": "Stock Entry"},
    ]
    return columns, rows
