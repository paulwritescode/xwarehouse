import frappe


def execute(filters=None):
    filters = filters or {}
    conditions = ["si.docstatus = 1"]
    values = {}
    for field in ["customer", "source_warehouse"]:
        if filters.get(field):
            conditions.append(f"si.{field} = %({field})s")
            values[field] = filters[field]
    for field, operator in [("from_date", ">="), ("to_date", "<=")]:
        if filters.get(field):
            conditions.append(f"si.posting_date {operator} %({field})s")
            values[field] = filters[field]
    rows = frappe.db.sql(
        f"""
        SELECT si.name AS sales_issue, si.posting_date, si.customer,
            si.source_warehouse, si.total_revenue, si.total_cost,
            si.expected_profit, si.margin_percent
        FROM `tabSales Issue` si
        WHERE {" AND ".join(conditions)}
        ORDER BY si.posting_date DESC, si.name DESC
        """,
        values,
        as_dict=True,
    )
    columns = [
        {"label": "Sales Issue", "fieldname": "sales_issue", "fieldtype": "Link", "options": "Sales Issue"},
        {"label": "Date", "fieldname": "posting_date", "fieldtype": "Date"},
        {"label": "Customer", "fieldname": "customer", "fieldtype": "Link", "options": "Customer"},
        {"label": "Warehouse", "fieldname": "source_warehouse", "fieldtype": "Link", "options": "Warehouse"},
        {"label": "Expected Revenue", "fieldname": "total_revenue", "fieldtype": "Currency"},
        {"label": "Cost", "fieldname": "total_cost", "fieldtype": "Currency"},
        {"label": "Expected Profit", "fieldname": "expected_profit", "fieldtype": "Currency"},
        {"label": "Margin %", "fieldname": "margin_percent", "fieldtype": "Percent"},
    ]
    return columns, rows
