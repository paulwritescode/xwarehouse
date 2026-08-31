import frappe


def execute(filters=None):
    filters = filters or {}

    conditions = ["1=1"]
    values = {}

    for field in ["item", "warehouse"]:
        if filters.get(field):
            conditions.append(
                f"sle.{field} = %({field})s"
            )
            values[field] = filters[field]

    rows = frappe.db.sql(
        f"""
        SELECT
            sle.posting_date,
            sle.posting_time,
            item.item_code,
            item.item_name,
            warehouse.warehouse_name,
            sle.actual_qty,
            sle.incoming_rate,
            sle.valuation_rate,
            sle.qty_after_transaction,
            sle.stock_value,
            sle.stock_entry
        FROM `tabStock Ledger Entry` sle
        INNER JOIN `tabItem` item ON item.name = sle.item
        INNER JOIN `tabWarehouse` warehouse ON warehouse.name = sle.warehouse
        WHERE {" AND ".join(conditions)}
        ORDER BY
            sle.posting_date,
            sle.posting_time,
            sle.creation
        """,
        values,
        as_dict=True,
    )

    columns = [
        {
            "label": "Date",
            "fieldname": "posting_date",
            "fieldtype": "Date",
        },
        {
            "label": "Time",
            "fieldname": "posting_time",
            "fieldtype": "Time",
        },
        {
            "label": "Item Code",
            "fieldname": "item_code",
            "fieldtype": "Data",
        },
        {
            "label": "Item Name",
            "fieldname": "item_name",
            "fieldtype": "Data",
        },
        {
            "label": "Warehouse",
            "fieldname": "warehouse_name",
            "fieldtype": "Data",
        },
        {
            "label": "Quantity Change",
            "fieldname": "actual_qty",
            "fieldtype": "Float",
        },
        {
            "label": "Incoming Rate",
            "fieldname": "incoming_rate",
            "fieldtype": "Currency",
        },
        {
            "label": "Valuation Rate",
            "fieldname": "valuation_rate",
            "fieldtype": "Currency",
        },
        {
            "label": "Balance After Transaction",
            "fieldname": "qty_after_transaction",
            "fieldtype": "Float",
        },
        {
            "label": "Stock Value",
            "fieldname": "stock_value",
            "fieldtype": "Currency",
        },
        {
            "label": "Stock Entry",
            "fieldname": "stock_entry",
            "fieldtype": "Link",
            "options": "Stock Entry",
        },
    ]

    return columns, rows
