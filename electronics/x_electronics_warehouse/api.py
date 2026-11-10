import frappe
import json

from electronics.x_electronics_warehouse.stock import get_balance


def _require_read_access():
	for doctype in ("Item", "Warehouse"):
		if not frappe.has_permission(doctype, ptype="read"):
			frappe.throw("You do not have permission to view warehouse data.", frappe.PermissionError)


def _resolve_item(item):
	item = (item or "").strip()
	if not item:
		frappe.throw("An item code or item name is required.")

	rows = frappe.get_all(
		"Item",
		or_filters=[
			{"name": item},
			{"item_code": item},
			{"item_name": ["like", f"%{item}%"]},
		],
		fields=["name", "item_code", "item_name", "unit"],
		limit_page_length=10,
	)
	if not rows:
		frappe.throw(f"No item matched '{item}'.")

	exact = next(
		(row for row in rows if row.name == item or row.item_code == item),
		None,
	)
	if exact:
		return exact
	if len(rows) > 1:
		matches = ", ".join(row.item_code for row in rows[:5])
		frappe.throw(f"More than one item matched '{item}'. Choose one of: {matches}.")
	return rows[0]


@frappe.whitelist()
def get_stock_balance(item, warehouse):
	"""Return the current balance for one item in one warehouse."""
	_require_read_access()
	return get_balance(item, warehouse)


@frappe.whitelist()
def get_warehouse_summary():
	"""Return the count and names of physical (non-group) warehouses."""
	_require_read_access()
	warehouses = frappe.get_all(
		"Warehouse",
		filters={"is_group": 0},
		fields=["name", "warehouse_name"],
		order_by="warehouse_name asc",
		limit_page_length=100,
	)
	return {
		"count": frappe.db.count("Warehouse", {"is_group": 0}),
		"warehouses": [
			{"name": row.name, "warehouse_name": row.warehouse_name}
			for row in warehouses
		],
	}


@frappe.whitelist()
def get_item_stock_overall(item):
	"""Return the current quantity of an item across all physical warehouses."""
	_require_read_access()
	item_doc = _resolve_item(item)

	from electronics.x_electronics_warehouse.report.stock_balance.stock_balance import execute

	_, balances = execute({"to_date": frappe.utils.today(), "item": item_doc.name})
	by_warehouse = {}
	for row in balances:
		bucket = by_warehouse.setdefault(
			row.warehouse,
			{
				"warehouse": row.warehouse,
				"warehouse_name": row.warehouse_name,
				"qty": 0,
				"value": 0,
			},
		)
		bucket["qty"] += row.qty or 0
		bucket["value"] += row.value or 0

	warehouses = sorted(by_warehouse.values(), key=lambda row: row["warehouse_name"])
	qty = sum(row["qty"] for row in warehouses)
	value = sum(row["value"] for row in warehouses)
	return {
		"item": item_doc.name,
		"item_code": item_doc.item_code,
		"item_name": item_doc.item_name,
		"unit": item_doc.unit,
		"qty": qty,
		"value": value,
		"rate": value / qty if qty else 0,
		"warehouses": warehouses,
	}


@frappe.whitelist()
def get_low_stock(item=None, warehouse=None):
	"""Return item/warehouse balances at or below their reorder levels."""
	_require_read_access()

	from electronics.x_electronics_warehouse.report.low_stock.low_stock import execute

	_, rows = execute({"item": item, "warehouse": warehouse})
	return rows


@frappe.whitelist()
def get_sales_summary(from_date=None, to_date=None, warehouse=None):
	"""Return submitted sales totals for a date range, defaulting to today."""
	_require_read_access()
	if not frappe.has_permission("Sales Issue", ptype="read"):
		frappe.throw("You do not have permission to view sales.", frappe.PermissionError)

	from electronics.x_electronics_warehouse.report.sales_profit.sales_profit import execute

	from_date = from_date or frappe.utils.today()
	to_date = to_date or from_date
	_, rows = execute(
		{
			"from_date": from_date,
			"to_date": to_date,
			"source_warehouse": warehouse,
		}
	)
	return {
		"from_date": from_date,
		"to_date": to_date,
		"warehouse": warehouse,
		"sales_count": len(rows),
		"revenue": sum(row.total_revenue or 0 for row in rows),
		"cost": sum(row.total_cost or 0 for row in rows),
		"profit": sum(row.expected_profit or 0 for row in rows),
		"sales": rows[:20],
	}


@frappe.whitelist()
def get_stock_discrepancies(warehouse=None):
	"""Return recorded, submitted stock-count variances; never infer fraud."""
	_require_read_access()
	if not frappe.has_permission("Stock Count", ptype="read"):
		frappe.throw("You do not have permission to view stock counts.", frappe.PermissionError)

	from electronics.x_electronics_warehouse.report.stock_discrepancy.stock_discrepancy import execute

	_, rows = execute({"warehouse": warehouse})
	return {
		"warehouse": warehouse,
		"discrepancy_count": len(rows),
		"absolute_quantity_variance": sum(abs(row.variance or 0) for row in rows),
		"absolute_value_variance": sum(abs(row.variance_value or 0) for row in rows),
		"discrepancies": rows[:20],
		"note": "A stock discrepancy is a recorded variance, not proof of fraud.",
	}


@frappe.whitelist()
def get_dashboard_summary():
	_require_read_access()

	from electronics.x_electronics_warehouse.report.stock_balance.stock_balance import execute

	_, balances = execute({"to_date": frappe.utils.today()})
	from electronics.x_electronics_warehouse.report.low_stock.low_stock import execute as execute_low_stock

	_, low_stock = execute_low_stock({})

	return {
		"item_count": frappe.db.count("Item"),
		"warehouse_count": frappe.db.count("Warehouse", {"is_group": 0}),
		"stock_value": sum(row.value or 0 for row in balances),
		"quantity": sum(row.qty or 0 for row in balances),
		"low_stock_count": len(low_stock),
	}


def _require_call_access():
	if frappe.session.user == "Guest":
		frappe.throw("Please log in to access warehouse call sessions.", frappe.PermissionError)
	if frappe.session.user != "Administrator" and not (
		frappe.has_role("System Manager") or frappe.has_role("Warehouse Manager")
	):
		frappe.throw("Only an administrator or Warehouse Manager can access call sessions.", frappe.PermissionError)


def _build_daily_admin_summary():
	"""Build a factual, read-only snapshot for the administrator call."""
	dashboard = get_dashboard_summary()
	sales = get_sales_summary()
	discrepancies = get_stock_discrepancies()
	low_stock = get_low_stock()

	return {
		"date": frappe.utils.today(),
		"dashboard": dashboard,
		"sales": {
			"sales_count": sales["sales_count"],
			"revenue": sales["revenue"],
			"cost": sales["cost"],
			"profit": sales["profit"],
		},
		"low_stock": low_stock[:20],
		"discrepancies": discrepancies["discrepancies"],
		"discrepancy_count": discrepancies["discrepancy_count"],
		"note": "Recorded stock discrepancies are not proof of fraud.",
	}


def _summary_text(summary):
	dashboard = summary["dashboard"]
	sales = summary["sales"]
	low_stock_count = len(summary["low_stock"])
	discrepancy_count = summary["discrepancy_count"]
	return (
		f"Daily warehouse summary for {summary['date']}. "
		f"{dashboard['warehouse_count']} physical warehouses hold "
		f"{dashboard['quantity']} units across {dashboard['item_count']} items. "
		f"Today's sales: {sales['sales_count']} transactions, "
		f"revenue {sales['revenue']}, expected profit {sales['profit']}. "
		f"There are {low_stock_count} low-stock lines and "
		f"{discrepancy_count} recorded stock discrepancies to review."
	)


@frappe.whitelist()
def create_daily_admin_call_session():
	"""Create or return today's administrator summary call session."""
	_require_call_access()
	today = frappe.utils.today()
	name = f"ADMIN-SUMMARY-{today}"
	if frappe.db.exists("Voice Call Session", name):
		return frappe.get_doc("Voice Call Session", name).as_dict()

	summary = _build_daily_admin_summary()
	scheduled_for = f"{today} 17:00:00"
	session = frappe.get_doc(
		{
			"doctype": "Voice Call Session",
			"name": name,
			"session_key": name,
			"session_type": "Daily Administrator Summary",
			"status": "Scheduled",
			"scheduled_for": scheduled_for,
			"recipient": "Administrator",
			"summary_title": f"Warehouse closeout — {today}",
			"summary_text": _summary_text(summary),
			"summary_json": json.dumps(summary, default=str),
			"public_token": frappe.generate_hash(length=32),
		}
	).insert(ignore_permissions=True)
	frappe.db.commit()
	return session.as_dict()


@frappe.whitelist()
def get_latest_admin_call_session():
	"""Return the latest administrator call session for the Vue/PWA screen."""
	_require_call_access()
	name = frappe.db.get_value(
		"Voice Call Session",
		{"recipient": frappe.session.user, "session_type": "Daily Administrator Summary"},
		"name",
		order_by="scheduled_for desc",
	)
	if not name and frappe.session.user == "Administrator":
		name = frappe.db.get_value(
			"Voice Call Session",
			{"recipient": "Administrator", "session_type": "Daily Administrator Summary"},
			"name",
			order_by="scheduled_for desc",
		)
	if not name:
		return None
	return frappe.get_doc("Voice Call Session", name).as_dict()


@frappe.whitelist()
def update_admin_call_session(name, status):
	"""Move a call session through the small, auditable call lifecycle."""
	_require_call_access()
	if status not in {"In Progress", "Completed", "Declined"}:
		frappe.throw("Unsupported call session status.")
	session = frappe.get_doc("Voice Call Session", name)
	if status == "In Progress":
		session.started_at = frappe.utils.now_datetime()
	if status in {"Completed", "Declined"}:
		session.ended_at = frappe.utils.now_datetime()
	session.status = status
	session.save(ignore_permissions=True)
	frappe.db.commit()
	return session.as_dict()


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
