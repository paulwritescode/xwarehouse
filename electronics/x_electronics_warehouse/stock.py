import frappe


def get_balance(item, warehouse):
    row = frappe.db.get_value(
        "Stock Ledger Entry",
        {
            "item": item,
            "warehouse": warehouse,
        },
        [
            "qty_after_transaction",
            "stock_value",
            "valuation_rate",
        ],
        order_by="posting_date desc, posting_time desc, creation desc",
        as_dict=True,
    )

    return {
        "qty": row.qty_after_transaction if row else 0,
        "value": row.stock_value if row else 0,
        "rate": row.valuation_rate if row else 0,
    }


def add_stock(stock_entry, item, warehouse, qty, incoming_rate):
    old = get_balance(item, warehouse)

    new_qty = old["qty"] + qty

    if new_qty < 0:
        frappe.throw("Stock cannot become negative.")

    if qty > 0:
        new_value = old["value"] + (qty * incoming_rate)
    else:
        new_value = new_qty * old["rate"]

    new_rate = new_value / new_qty if new_qty else 0

    ledger_entry = frappe.get_doc({
        "doctype": "Stock Ledger Entry",
        "posting_date": stock_entry.posting_date,
        "posting_time": stock_entry.posting_time,
        "item": item,
        "warehouse": warehouse,
        "actual_qty": qty,
        "incoming_rate": incoming_rate,
        "valuation_rate": new_rate,
        "qty_after_transaction": new_qty,
        "stock_value": new_value,
        "stock_entry": stock_entry.name,
    })

    ledger_entry.insert(ignore_permissions=True)

    return ledger_entry