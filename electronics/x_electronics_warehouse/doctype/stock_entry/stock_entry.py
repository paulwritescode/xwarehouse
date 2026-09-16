# Copyright (c) 2026, kinyattipaul@gmail.com and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

from electronics.x_electronics_warehouse.stock import add_stock, get_balance, reverse_stock


class StockEntry(Document):
	def validate(self):
		if not self.items:
			frappe.throw("Add at least one item.")

		if self.purpose not in {"Receipt", "Opening Stock", "Consume", "Transfer", "Adjustment"}:
			frappe.throw("Select a valid stock entry purpose.")

		if self.supplier and self.purpose not in {"Receipt", "Opening Stock"}:
			frappe.throw("Supplier can only be set on a Receipt or Opening Stock entry.")

		if self.customer and self.purpose != "Consume":
			frappe.throw("Customer can only be set on a Consume entry.")

		if self.checked_out_to and self.purpose != "Consume":
			frappe.throw("Checked Out To can only be set on a Consume entry.")

		if self.stock_count and self.purpose != "Adjustment":
			frappe.throw("Stock Count can only be set on an Adjustment entry.")

		if self.purpose == "Adjustment" and not self.adjustment_reason:
			frappe.throw("Adjustment entries need a reason.")

		if self.purpose != "Transfer" and self.approval_status == "Pending Approval":
			self.approval_status = "Approved"

		for row in self.items:
			if not row.item:
				frappe.throw("Each item row must have an Item.")

			tracking_method = frappe.db.get_value("Item", row.item, "tracking_method") or "None"
			if row.batch_no and row.serial_no:
				frappe.throw(f"{row.item} cannot have both a batch number and a serial number.")
			if tracking_method == "Batch" and not row.batch_no:
				frappe.throw(f"Batch number is required for {row.item}.")
			if tracking_method == "Serial":
				if not row.serial_no:
					frappe.throw(f"Serial number is required for {row.item}.")
				if row.qty != 1:
					frappe.throw(f"Serial-tracked item {row.item} must have quantity 1 per row.")
			if tracking_method == "None" and (row.batch_no or row.serial_no):
				frappe.throw(f"{row.item} is not configured for batch or serial tracking.")

			if row.qty is None or row.qty <= 0:
				frappe.throw(f"Quantity for {row.item} must be greater than zero.")

			if self.purpose in {"Receipt", "Opening Stock"} and (row.rate is None or row.rate <= 0):
				frappe.throw(f"Incoming rate for {row.item} must be greater than zero.")

			if self.purpose == "Adjustment":
				if row.adjustment_direction not in {"Increase", "Decrease"}:
					frappe.throw(f"Adjustment direction is required for {row.item}.")
				if row.adjustment_direction == "Increase" and (row.rate is None or row.rate <= 0):
					frappe.throw(f"Rate is required for an increase of {row.item}.")

		if self.purpose in {"Receipt", "Opening Stock"}:
			if not self.target_warehouse:
				frappe.throw("Receipt needs a target warehouse.")

		if self.purpose == "Consume":
			if not self.source_warehouse:
				frappe.throw("Consume needs a source warehouse.")

		if self.purpose == "Transfer":
			if not self.source_warehouse or not self.target_warehouse:
				frappe.throw("Transfer needs source and target warehouses.")

			if self.source_warehouse == self.target_warehouse:
				frappe.throw("Source and target warehouses must be different.")

		if self.purpose == "Adjustment":
			if not self.source_warehouse or not self.target_warehouse:
				frappe.throw("Adjustment needs a warehouse.")
			if self.source_warehouse != self.target_warehouse:
				frappe.throw("Adjustment source and target warehouses must match.")

		if self.purpose in ["Consume", "Transfer"] or self.purpose == "Adjustment":
			for row in self.items:
				if self.purpose == "Adjustment" and row.adjustment_direction == "Increase":
					continue
				balance = get_balance(
					row.item,
					self.source_warehouse,
					batch_no=row.batch_no,
					serial_no=row.serial_no,
				)

				if row.qty > balance["qty"]:
					frappe.throw(
						f"Not enough {row.item}. Available: {balance['qty']}"
					)

	def on_submit(self):
		for row in self.items:
			if self.purpose in {"Receipt", "Opening Stock"}:
				add_stock(
					self,
					row.item,
					self.target_warehouse,
					row.qty,
					row.rate,
					batch_no=row.batch_no,
					serial_no=row.serial_no,
				)

			elif self.purpose == "Adjustment":
				if row.adjustment_direction == "Increase":
					add_stock(
						self,
						row.item,
						self.target_warehouse,
						row.qty,
						row.rate,
						batch_no=row.batch_no,
						serial_no=row.serial_no,
					)
				else:
					add_stock(
						self,
						row.item,
						self.source_warehouse,
						-row.qty,
						0,
						batch_no=row.batch_no,
						serial_no=row.serial_no,
					)

			elif self.purpose == "Consume":
				add_stock(
					self,
					row.item,
					self.source_warehouse,
					-row.qty,
					0,
					batch_no=row.batch_no,
					serial_no=row.serial_no,
				)

			elif self.purpose == "Transfer":
				source_balance = get_balance(
					row.item,
					self.source_warehouse,
					batch_no=row.batch_no,
					serial_no=row.serial_no,
				)
				add_stock(
					self,
					row.item,
					self.source_warehouse,
					-row.qty,
					0,
					batch_no=row.batch_no,
					serial_no=row.serial_no,
				)
				add_stock(
					self,
					row.item,
					self.target_warehouse,
					row.qty,
					source_balance["rate"],
					batch_no=row.batch_no,
					serial_no=row.serial_no,
				)

	def before_submit(self):
		if self.purpose == "Transfer" and self.approval_status != "Approved":
			frappe.throw("Transfer Stock Entries must be approved before submission.")

	def before_cancel(self):
		entries = frappe.get_all(
			"Stock Ledger Entry",
			filters={"stock_entry": self.name, "is_reversal": 0},
			fields=["name"],
		)
		if not entries:
			frappe.throw("This Stock Entry has no stock movements to reverse.")

	def on_cancel(self):
		reverse_stock(self)
