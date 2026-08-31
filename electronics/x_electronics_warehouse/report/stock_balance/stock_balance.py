import frappe


def execute(filters=None):
    filters = filters or {}

    conditions = [
        "sle.posting_date <= %(to_date)s"
    ]

    values = {
        "to_date": filters.get("to_date")
        or frappe.utils.today()
    }

    for field in ["item", "warehouse"]:
        if filters.get(field):
            conditions.append(
                f"sle.{field} = %({field})s"
            )
            values[field] = filters[field]

    rows = frappe.db.sql(
        f"""
        SELECT
            item.item_code,
            item.item_name,
            warehouse.warehouse_name,
            sle.qty_after_transaction AS qty,
            sle.valuation_rate AS rate,
            sle.stock_value AS value
        FROM `tabStock Ledger Entry` sle
        INNER JOIN `tabItem` item ON item.name = sle.item
        INNER JOIN `tabWarehouse` warehouse ON warehouse.name = sle.warehouse
        INNER JOIN (
            SELECT
                item,
                warehouse,
                MAX(
                    CONCAT(
                        posting_date,
                        ' ',
                        posting_time,
                        ' ',
                        creation
                    )
                ) AS last_row
            FROM `tabStock Ledger Entry` sle
            WHERE {" AND ".join(conditions)}
            GROUP BY item, warehouse
        ) latest
        ON latest.item = sle.item
        AND latest.warehouse = sle.warehouse
        AND CONCAT(
            sle.posting_date,
            ' ',
            sle.posting_time,
            ' ',
            sle.creation
        ) = latest.last_row
        ORDER BY sle.item, sle.warehouse
        """,
        values,
        as_dict=True,
    )

    columns = [
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
            "label": "Quantity In Stock",
            "fieldname": "qty",
            "fieldtype": "Float",
        },
        {
            "label": "Moving Average Rate",
            "fieldname": "rate",
            "fieldtype": "Currency",
        },
        {
            "label": "Stock Value",
            "fieldname": "value",
            "fieldtype": "Currency",
        },
    ]

    return columns, rows
