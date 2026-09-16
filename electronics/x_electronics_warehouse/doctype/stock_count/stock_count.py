import frappe
from frappe.model.document import Document

from electronics.x_electronics_warehouse.stock import get_balance


class StockCount(Document):
    def validate(self):
        if not self.warehouse:
            frappe.throw("Stock Count needs a warehouse.")
        if not self.items:
            frappe.throw("Add at least one item to count.")
        if not self.counted_by:
            self.counted_by = frappe.session.user

        total_discrepancy_qty = 0
        total_discrepancy_value = 0
        for row in self.items:
            if not row.item:
                frappe.throw("Each count row must have an Item.")
            balance = get_balance(
                row.item,
                self.warehouse,
                batch_no=row.batch_no,
                serial_no=row.serial_no,
            )
            if self.is_new() and row.system_qty is None:
                row.system_qty = balance["qty"]
                row.valuation_rate = balance["rate"]
            if row.counted_qty is None or row.counted_qty < 0:
                frappe.throw(f"Counted quantity for {row.item} cannot be negative.")
            row.variance = row.counted_qty - (row.system_qty or 0)
            row.variance_value = row.variance * (row.valuation_rate or balance["rate"])
            total_discrepancy_qty += abs(row.variance)
            total_discrepancy_value += abs(row.variance_value)

        self.has_discrepancy = 1 if total_discrepancy_qty else 0
        self.discrepancy_qty = total_discrepancy_qty
        self.discrepancy_value = total_discrepancy_value

    def on_submit(self):
        adjustment_rows = []
        for row in self.items:
            if not row.variance:
                continue
            adjustment_rows.append(
                {
                    "item": row.item,
                    "qty": abs(row.variance),
                    "rate": row.valuation_rate,
                    "adjustment_direction": "Increase" if row.variance > 0 else "Decrease",
                    "batch_no": row.batch_no,
                    "serial_no": row.serial_no,
                }
            )

        if not adjustment_rows:
            self.db_set("status", "No Variance")
            return

        stock_entry = frappe.get_doc(
            {
                "doctype": "Stock Entry",
                "posting_date": self.count_date,
                "posting_time": self.count_time,
                "purpose": "Adjustment",
                "source_warehouse": self.warehouse,
                "target_warehouse": self.warehouse,
                "stock_count": self.name,
                "adjustment_reason": self.reason or "Stock count variance",
                "items": adjustment_rows,
            }
        )
        stock_entry.insert(ignore_permissions=True)
        stock_entry.submit()
        self.db_set("adjustment_stock_entry", stock_entry.name)
        self.db_set("status", "Adjusted")

    def before_cancel(self):
        if self.adjustment_stock_entry:
            return
        if self.status != "No Variance":
            frappe.throw("This Stock Count has no adjustment to cancel.")

    def on_cancel(self):
        if self.adjustment_stock_entry:
            frappe.get_doc("Stock Entry", self.adjustment_stock_entry).cancel()
        self.db_set("status", "Cancelled")
