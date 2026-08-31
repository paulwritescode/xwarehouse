# Copyright (c) 2026, kinyattipaul@gmail.com and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

from electronics.x_electronics_warehouse.stock import (
    add_stock,
    get_balance,
)

class StockEntry(Document):
    def validate(self):
        if not self.items:
            frappe.throw("Add at least one item.")

        if self.purpose == "Receipt":
            if not self.target_warehouse:
                frappe.throw("Receipt needs a target warehouse.")

        if self.purpose == "Consume":
            if not self.source_warehouse:
                frappe.throw("Consume needs a source warehouse.")

        if self.purpose == "Transfer":
            if not self.source_warehouse or not self.target_warehouse:
                frappe.throw(
                    "Transfer needs source and target warehouses."
                )

            if self.source_warehouse == self.target_warehouse:
                frappe.throw(
                    "Source and target warehouses must be different."
                )

        if self.purpose in ["Consume", "Transfer"]:
            for row in self.items:
                balance = get_balance(
                    row.item,
                    self.source_warehouse,
                )

                if row.qty <= 0:
                    frappe.throw("Quantity must be greater than zero.")

                if row.qty > balance["qty"]:
                    frappe.throw(
                        f"Not enough {row.item}. "
                        f"Available: {balance['qty']}"
                    )

    def on_submit(self):
        for row in self.items:
            if self.purpose == "Receipt":
                add_stock(
                    self,
                    row.item,
                    self.target_warehouse,
                    row.qty,
                    row.rate,
                )

            elif self.purpose == "Consume":
                add_stock(
                    self,
                    row.item,
                    self.source_warehouse,
                    -row.qty,
                    0,
                )

            elif self.purpose == "Transfer":
                source_balance = get_balance(
                    row.item,
                    self.source_warehouse,
                )

                add_stock(
                    self,
                    row.item,
                    self.source_warehouse,
                    -row.qty,
                    0,
                )

                add_stock(
                    self,
                    row.item,
                    self.target_warehouse,
                    row.qty,
                    source_balance["rate"],
                )

    def before_cancel(self):
        frappe.throw(
            "Submitted stock entries are permanent "
            "and cannot be cancelled."
        )