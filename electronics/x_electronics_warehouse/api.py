import frappe

from electronics.x_electronics_warehouse.stock import get_balance


def _require_read_access():
	if not frappe.has_permission("Item", ptype="read"):
		frappe.throw("You do not have permission to view stock.", frappe.PermissionError)


@frappe.whitelist()
def get_stock_balance(item, warehouse):
	"""Return the current balance for one item in one warehouse."""
	_require_read_access()
	return get_balance(item, warehouse)


@frappe.whitelist()
def get_low_stock(item=None, warehouse=None):
	"""Return item/warehouse balances at or below their reorder levels."""
	_require_read_access()

	from electronics.x_electronics_warehouse.report.low_stock.low_stock import execute

	_, rows = execute({"item": item, "warehouse": warehouse})
	return rows


@frappe.whitelist()
def get_dashboard_summary():
	_require_read_access()

	from electronics.x_electronics_warehouse.report.stock_balance.stock_balance import execute

	_, balances = execute({"to_date": frappe.utils.today()})
	from electronics.x_electronics_warehouse.report.low_stock.low_stock import execute as execute_low_stock

	_, low_stock = execute_low_stock({})

	return {
		"item_count": frappe.db.count("Item"),
		"warehouse_count": frappe.db.count("Warehouse"),
		"stock_value": sum(row.value or 0 for row in balances),
		"quantity": sum(row.qty or 0 for row in balances),
		"low_stock_count": len(low_stock),
	}


def create_low_stock_notifications():
	from electronics.x_electronics_warehouse.report.low_stock.low_stock import execute

	_, rows = execute({})
	if not rows:
		return

	today = frappe.utils.today()
	managers = frappe.get_all(
		"Has Role",
		filters={"role": "Warehouse Manager", "parenttype": "User"},
		pluck="parent",
	)
	summary = "<br>".join(
		f"{row.item_code} at {row.warehouse_name}: {row.qty} remaining "
		f"(reorder level {row.reorder_level})"
		for row in rows[:20]
	)

	for user in managers:
		subject = f"Low Stock Alert - {today}"
		if frappe.db.exists("Notification Log", {"for_user": user, "subject": subject}):
			continue
		frappe.get_doc(
			{
				"doctype": "Notification Log",
				"for_user": user,
				"type": "Alert",
				"subject": subject,
				"email_content": summary,
			}
		).insert(ignore_permissions=True)


@frappe.whitelist()
def approve_stock_entry(name):
	if not frappe.has_role("System Manager") and not frappe.has_role("Warehouse Manager"):
		frappe.throw("Only a Warehouse Manager can approve stock transfers.", frappe.PermissionError)

	entry = frappe.get_doc("Stock Entry", name)
	if entry.docstatus != 0:
		frappe.throw("Only draft Stock Entries can be approved.")
	if entry.purpose != "Transfer":
		frappe.throw("Only Transfer Stock Entries require approval.")

	entry.approval_status = "Approved"
	entry.approved_by = frappe.session.user
	entry.approved_on = frappe.utils.now_datetime()
	entry.save(ignore_permissions=True)
	return entry.name


@frappe.whitelist()
def reject_stock_entry(name):
	if not frappe.has_role("System Manager") and not frappe.has_role("Warehouse Manager"):
		frappe.throw("Only a Warehouse Manager can reject stock transfers.", frappe.PermissionError)

	entry = frappe.get_doc("Stock Entry", name)
	if entry.docstatus != 0:
		frappe.throw("Only draft Stock Entries can be rejected.")
	if entry.purpose != "Transfer":
		frappe.throw("Only Transfer Stock Entries require approval.")

	entry.approval_status = "Rejected"
	entry.approved_by = frappe.session.user
	entry.approved_on = frappe.utils.now_datetime()
	entry.save(ignore_permissions=True)
	return entry.name
