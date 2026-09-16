import frappe


def get_balance(item, warehouse, batch_no=None, serial_no=None):
    filters = {"item": item, "warehouse": warehouse}
    if batch_no:
        filters["batch_no"] = batch_no
    if serial_no:
        filters["serial_no"] = serial_no

    rows = frappe.get_all(
        "Stock Ledger Entry",
        filters=filters,
        fields=["qty_after_transaction", "stock_value", "valuation_rate", "batch_no", "serial_no"],
        order_by="posting_date desc, posting_time desc, creation desc",
    )
    if not rows:
        return {"qty": 0, "value": 0, "rate": 0}

    tracking_method = frappe.db.get_value("Item", item, "tracking_method")
    if tracking_method in {"Batch", "Serial"} and not (batch_no or serial_no):
        latest_by_identifier = {}
        for row in rows:
            identifier = row.batch_no if tracking_method == "Batch" else row.serial_no
            if identifier not in latest_by_identifier:
                latest_by_identifier[identifier] = row
        rows = list(latest_by_identifier.values())
        value = sum(row.stock_value or 0 for row in rows)
        qty = sum(row.qty_after_transaction or 0 for row in rows)
        return {"qty": qty, "value": value, "rate": value / qty if qty else 0}

    row = rows[0]
    return {
        "qty": row.qty_after_transaction or 0,
        "value": row.stock_value or 0,
        "rate": row.valuation_rate or 0,
    }


def add_stock(
    stock_entry,
    item,
    warehouse,
    qty,
    incoming_rate,
    reversal_of=None,
    batch_no=None,
    serial_no=None,
):
    old = get_balance(item, warehouse, batch_no=batch_no, serial_no=serial_no)
    new_qty = old["qty"] + qty

    if new_qty < 0:
        frappe.throw("Stock cannot become negative.")

    if qty > 0:
        new_value = old["value"] + (qty * incoming_rate)
    else:
        new_value = new_qty * old["rate"]

    new_rate = new_value / new_qty if new_qty else 0

    ledger_entry = frappe.get_doc(
        {
            "doctype": "Stock Ledger Entry",
            "posting_date": stock_entry.posting_date,
            "posting_time": stock_entry.posting_time,
            "item": item,
            "warehouse": warehouse,
            "batch_no": batch_no,
            "serial_no": serial_no,
            "actual_qty": qty,
            "incoming_rate": incoming_rate,
            "valuation_rate": new_rate,
            "qty_after_transaction": new_qty,
            "stock_value": new_value,
            "stock_entry": stock_entry.name,
            "is_reversal": 1 if reversal_of else 0,
            "reversal_of": reversal_of,
        }
    )
    ledger_entry.flags.from_stock_entry = True
    ledger_entry.insert(ignore_permissions=True)

    return ledger_entry


def reverse_stock(stock_entry):
    entries = frappe.get_all(
        "Stock Ledger Entry",
        filters={"stock_entry": stock_entry.name, "is_reversal": 0},
        fields=[
            "name",
            "item",
            "warehouse",
            "actual_qty",
            "valuation_rate",
            "creation",
            "batch_no",
            "serial_no",
        ],
        order_by="creation desc",
    )

    if not entries:
        frappe.throw("No stock ledger entries were found for this Stock Entry.")

    for entry in entries:
        later_entry = frappe.db.exists(
            "Stock Ledger Entry",
            {
                "item": entry.item,
                "warehouse": entry.warehouse,
                "creation": [">", entry.creation],
                "stock_entry": ["!=", stock_entry.name],
            },
        )
        if later_entry:
            frappe.throw(
                f"Cannot cancel {stock_entry.name} because later stock movements exist "
                f"for {entry.item} in {entry.warehouse}."
            )

    for entry in entries:
        reverse_qty = -entry.actual_qty
        add_stock(
            stock_entry,
            entry.item,
            entry.warehouse,
            reverse_qty,
            entry.valuation_rate if reverse_qty > 0 else 0,
            entry.name,
            entry.batch_no,
            entry.serial_no,
        )
