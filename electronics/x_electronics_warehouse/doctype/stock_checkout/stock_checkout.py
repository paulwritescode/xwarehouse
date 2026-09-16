import frappe
from frappe.model.document import Document

from electronics.x_electronics_warehouse.stock import get_balance


class StockCheckout(Document):
    def validate(self):
        if not self.checked_out_to:
            frappe.throw("Stock Checkout needs the person receiving the stock.")
        if not self.warehouse:
            frappe.throw("Stock Checkout needs a warehouse.")
        if not self.items:
            frappe.throw("Add at least one item.")

        if not self.issued_by:
            self.issued_by = frappe.session.user

        for row in self.items:
            if row.qty is None or row.qty <= 0:
                frappe.throw(f"Quantity for {row.item} must be greater than zero.")
            if row.returned_qty and row.returned_qty > row.qty:
                frappe.throw(f"Returned quantity cannot exceed checkout quantity for {row.item}.")
            if not row.outstanding_qty:
                row.outstanding_qty = row.qty - (row.returned_qty or 0)

    def on_submit(self):
        stock_entry = frappe.get_doc(
            {
                "doctype": "Stock Entry",
                "posting_date": self.checkout_date,
                "posting_time": self.checkout_time,
                "purpose": "Consume",
                "source_warehouse": self.warehouse,
                "checked_out_to": self.checked_out_to,
                "items": [
                    {
                        "item": row.item,
                        "qty": row.qty,
                        "batch_no": row.batch_no,
                        "serial_no": row.serial_no,
                    }
                    for row in self.items
                ],
            }
        )
        stock_entry.insert(ignore_permissions=True)
        stock_entry.submit()

        for row in self.items:
            balance = get_balance(
                row.item,
                self.warehouse,
                batch_no=row.batch_no,
                serial_no=row.serial_no,
            )
            row.rate = balance["rate"]
            row.returned_qty = 0
            row.outstanding_qty = row.qty
            frappe.db.set_value(
                "Stock Checkout Item",
                row.name,
                {"rate": row.rate, "returned_qty": 0, "outstanding_qty": row.qty},
            )
        self.db_set("status", "Checked Out")
        self.db_set("stock_entry", stock_entry.name)

    def before_cancel(self):
        if not self.stock_entry:
            frappe.throw("This Stock Checkout has no Stock Entry to reverse.")

    def on_cancel(self):
        frappe.get_doc("Stock Entry", self.stock_entry).cancel()
