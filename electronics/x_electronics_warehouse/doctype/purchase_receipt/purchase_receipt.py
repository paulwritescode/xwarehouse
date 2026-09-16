import frappe
from frappe.model.document import Document


class PurchaseReceipt(Document):
    def validate(self):
        if not self.supplier:
            frappe.throw("Purchase Receipt needs a supplier.")
        if not self.target_warehouse:
            frappe.throw("Purchase Receipt needs a target warehouse.")
        if not self.items:
            frappe.throw("Add at least one item.")
        for row in self.items:
            if not row.item:
                frappe.throw("Each item row must have an Item.")
            if row.qty is None or row.qty <= 0:
                frappe.throw(f"Quantity for {row.item} must be greater than zero.")
            if row.rate is None or row.rate <= 0:
                frappe.throw(f"Rate for {row.item} must be greater than zero.")

    def on_submit(self):
        stock_entry = frappe.get_doc(
            {
                "doctype": "Stock Entry",
                "posting_date": self.posting_date,
                "posting_time": self.posting_time,
                "purpose": "Receipt",
                "supplier": self.supplier,
                "target_warehouse": self.target_warehouse,
                "items": [
                    {
                        "item": row.item,
                        "qty": row.qty,
                        "rate": row.rate,
                        "batch_no": row.batch_no,
                        "serial_no": row.serial_no,
                    }
                    for row in self.items
                ],
            }
        )
        stock_entry.insert(ignore_permissions=True)
        stock_entry.submit()
        self.db_set("stock_entry", stock_entry.name)

    def before_cancel(self):
        if not self.stock_entry:
            frappe.throw("This Purchase Receipt has no Stock Entry to reverse.")

    def on_cancel(self):
        frappe.get_doc("Stock Entry", self.stock_entry).cancel()
