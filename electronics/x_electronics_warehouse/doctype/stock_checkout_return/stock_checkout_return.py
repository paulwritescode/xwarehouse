import frappe
from frappe.model.document import Document


class StockCheckoutReturn(Document):
    def validate(self):
        if not self.checkout:
            frappe.throw("Checkout Return needs a Stock Checkout.")
        if not self.items:
            frappe.throw("Add at least one returned item.")

        checkout = frappe.get_doc("Stock Checkout", self.checkout)
        if checkout.docstatus != 1:
            frappe.throw("Only submitted Stock Checkouts can receive returns.")

        checkout_items = {row.name: row for row in checkout.items}
        for row in self.items:
            checkout_item = checkout_items.get(row.checkout_item)
            if not checkout_item:
                frappe.throw("Each return row must reference an item from the Checkout.")
            if row.qty is None or row.qty <= 0:
                frappe.throw("Returned quantity must be greater than zero.")
            if row.qty > checkout_item.outstanding_qty:
                frappe.throw(
                    f"Cannot return more than the outstanding quantity for {checkout_item.item}."
                )

    def on_submit(self):
        checkout = frappe.get_doc("Stock Checkout", self.checkout)
        checkout_items = {row.name: row for row in checkout.items}
        stock_entry = frappe.get_doc(
            {
                "doctype": "Stock Entry",
                "posting_date": self.return_date,
                "posting_time": self.return_time,
                "purpose": "Receipt",
                "target_warehouse": checkout.warehouse,
                "items": [
                    {
                        "item": checkout_items[row.checkout_item].item,
                        "qty": row.qty,
                        "rate": checkout_items[row.checkout_item].rate,
                        "batch_no": checkout_items[row.checkout_item].batch_no,
                        "serial_no": checkout_items[row.checkout_item].serial_no,
                    }
                    for row in self.items
                ],
            }
        )
        stock_entry.insert(ignore_permissions=True)
        stock_entry.submit()

        for row in self.items:
            checkout_item = checkout_items[row.checkout_item]
            returned_qty = checkout_item.returned_qty + row.qty
            frappe.db.set_value(
                "Stock Checkout Item",
                checkout_item.name,
                {
                    "returned_qty": returned_qty,
                    "outstanding_qty": checkout_item.qty - returned_qty,
                },
            )

        outstanding = frappe.db.count(
            "Stock Checkout Item",
            {"parent": checkout.name, "outstanding_qty": [">", 0]},
        )
        frappe.db.set_value(
            "Stock Checkout",
            checkout.name,
            "status",
            "Partially Returned" if outstanding else "Returned",
        )
        self.db_set("stock_entry", stock_entry.name)

    def before_cancel(self):
        if not self.stock_entry:
            frappe.throw("This Checkout Return has no Stock Entry to reverse.")

    def on_cancel(self):
        frappe.get_doc("Stock Entry", self.stock_entry).cancel()
        checkout = frappe.get_doc("Stock Checkout", self.checkout)
        checkout_items = {row.name: row for row in checkout.items}
        for row in self.items:
            checkout_item = checkout_items[row.checkout_item]
            returned_qty = checkout_item.returned_qty - row.qty
            frappe.db.set_value(
                "Stock Checkout Item",
                checkout_item.name,
                {
                    "returned_qty": returned_qty,
                    "outstanding_qty": checkout_item.qty - returned_qty,
                },
            )
        frappe.db.set_value("Stock Checkout", checkout.name, "status", "Checked Out")
