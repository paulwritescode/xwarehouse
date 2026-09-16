# Copyright (c) 2026, kinyattipaul@gmail.com and contributors
# For license information, please see license.txt

# import frappe
import frappe
from frappe.model.document import Document


class StockLedgerEntry(Document):
	def before_insert(self):
		if not self.flags.get("from_stock_entry"):
			frappe.throw("Stock Ledger Entries are created automatically from Stock Entries.")

	def before_save(self):
		if not self.is_new() and not self.flags.get("from_stock_entry"):
			frappe.throw("Stock Ledger Entries are permanent and cannot be edited.")

	def on_trash(self):
		frappe.throw("Stock Ledger Entries are permanent and cannot be deleted.")
