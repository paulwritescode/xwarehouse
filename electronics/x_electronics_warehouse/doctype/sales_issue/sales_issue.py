import frappe
from frappe.model.document import Document

from electronics.x_electronics_warehouse.stock import get_balance


class SalesIssue(Document):
    def validate(self):
        if not self.customer:
            frappe.throw("Sales Issue needs a customer.")
        if not self.source_warehouse:
            frappe.throw("Sales Issue needs a source warehouse.")
        if not self.items:
            frappe.throw("Add at least one item.")
        for row in self.items:
            if not row.item:
                frappe.throw("Each item row must have an Item.")
            if row.qty is None or row.qty <= 0:
                frappe.throw(f"Quantity for {row.item} must be greater than zero.")
            if row.selling_rate is None or row.selling_rate <= 0:
                frappe.throw(f"Selling rate for {row.item} must be greater than zero.")

    def on_submit(self):
        total_revenue = 0
        total_cost = 0
        for row in self.items:
            balance = get_balance(
                row.item,
                self.source_warehouse,
                batch_no=row.batch_no,
                serial_no=row.serial_no,
            )
            total_revenue += row.qty * row.selling_rate
            total_cost += row.qty * balance["rate"]

        stock_entry = frappe.get_doc(
            {
                "doctype": "Stock Entry",
                "posting_date": self.posting_date,
                "posting_time": self.posting_time,
                "purpose": "Consume",
                "customer": self.customer,
                "source_warehouse": self.source_warehouse,
                "items": [
                    {
                        "item": row.item,
                        "qty": row.qty,
                        "rate": row.rate,
                        "selling_rate": row.selling_rate,
                        "batch_no": row.batch_no,
                        "serial_no": row.serial_no,
                    }
                    for row in self.items
                ],
            }
        )
        stock_entry.insert(ignore_permissions=True)
        stock_entry.submit()

        expected_profit = total_revenue - total_cost
        self.db_set("total_revenue", total_revenue)
        self.db_set("total_cost", total_cost)
        self.db_set("expected_profit", expected_profit)
        self.db_set(
            "margin_percent",
            (expected_profit / total_revenue * 100) if total_revenue else 0,
        )
        self.db_set("stock_entry", stock_entry.name)

    def before_cancel(self):
        if not self.stock_entry:
            frappe.throw("This Sales Issue has no Stock Entry to reverse.")

    def on_cancel(self):
        frappe.get_doc("Stock Entry", self.stock_entry).cancel()
