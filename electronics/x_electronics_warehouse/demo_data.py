"""Idempotent demo records for exercising XWarehouse voice queries."""

import frappe


DEMO_CUSTOMER = "DEMO-CUST-001"


def _get_or_create(doctype, filters, values):
	name = frappe.db.exists(doctype, filters)
	if name:
		return frappe.get_doc(doctype, name)
	return frappe.get_doc({"doctype": doctype, **values}).insert(ignore_permissions=True)


def _stock_entry(purpose, *, date, source=None, target=None, items, supplier=None):
	entry = frappe.get_doc(
		{
			"doctype": "Stock Entry",
			"posting_date": date,
			"posting_time": frappe.utils.nowtime(),
			"purpose": purpose,
			"source_warehouse": source,
			"target_warehouse": target,
			"supplier": supplier,
			"items": items,
		}
	).insert(ignore_permissions=True)
	if purpose == "Transfer":
		entry.approval_status = "Approved"
		entry.save(ignore_permissions=True)
	entry.submit()
	return entry


def seed_demo_data():
	"""Create a small, realistic warehouse dataset once and return its summary.

	The seed is intentionally namespaced with DEMO-/Demo so it is easy to identify
	and remove manually later. It uses normal submitted Stock Entries, Sales Issues,
	and Stock Counts so the same read-only reports used by the voice agent see it.
	"""
	if frappe.db.exists("Customer", DEMO_CUSTOMER):
		return {"created": False, "reason": "Demo data already exists."}

	today = frappe.utils.today()
	yesterday = frappe.utils.add_days(today, -1)

	warehouses = {
		"main": _get_or_create(
			"Warehouse",
			{"warehouse_name": "Demo Main Warehouse"},
			{"warehouse_name": "Demo Main Warehouse", "is_group": 0},
		),
		"overflow": _get_or_create(
			"Warehouse",
			{"warehouse_name": "Demo Overflow Warehouse"},
			{"warehouse_name": "Demo Overflow Warehouse", "is_group": 0},
		),
		"repair": _get_or_create(
			"Warehouse",
			{"warehouse_name": "Demo Repair Warehouse"},
			{"warehouse_name": "Demo Repair Warehouse", "is_group": 0},
		),
	}

	items = {
		"laptop": _get_or_create(
			"Item",
			{"item_code": "DEMO-LAPTOP-15"},
			{
				"item_code": "DEMO-LAPTOP-15",
				"item_name": "Demo Laptop 15",
				"unit": "NOS",
				"valuation_method": "Moving Average",
				"reorder_level": 5,
			},
		),
		"monitor": _get_or_create(
			"Item",
			{"item_code": "DEMO-MONITOR-24"},
			{
				"item_code": "DEMO-MONITOR-24",
				"item_name": "Demo Monitor 24",
				"unit": "NOS",
				"valuation_method": "Moving Average",
				"reorder_level": 10,
			},
		),
		"dock": _get_or_create(
			"Item",
			{"item_code": "DEMO-USB-C-DOCK"},
			{
				"item_code": "DEMO-USB-C-DOCK",
				"item_name": "Demo USB-C Dock",
				"unit": "NOS",
				"valuation_method": "Moving Average",
				"reorder_level": 25,
			},
		),
		"mouse": _get_or_create(
			"Item",
			{"item_code": "DEMO-WIRELESS-MOUSE"},
			{
				"item_code": "DEMO-WIRELESS-MOUSE",
				"item_name": "Demo Wireless Mouse",
				"unit": "NOS",
				"valuation_method": "Moving Average",
				"reorder_level": 20,
			},
		),
	}

	supplier = _get_or_create(
		"Supplier",
		{"supplier_code": "DEMO-SUP-001"},
		{"supplier_code": "DEMO-SUP-001", "supplier_name": "Demo Electronics Supplier"},
	)
	customer = _get_or_create(
		"Customer",
		{"customer_code": DEMO_CUSTOMER},
		{"customer_code": DEMO_CUSTOMER, "customer_name": "Demo Retail Customer"},
	)

	_stock_entry(
		"Receipt",
		date=yesterday,
		target=warehouses["main"].name,
		supplier=supplier.name,
		items=[
			{"item": items["laptop"].name, "qty": 40, "rate": 80000},
			{"item": items["monitor"].name, "qty": 70, "rate": 22000},
			{"item": items["dock"].name, "qty": 30, "rate": 9000},
			{"item": items["mouse"].name, "qty": 100, "rate": 2500},
		],
	)
	_stock_entry(
		"Receipt",
		date=yesterday,
		target=warehouses["overflow"].name,
		supplier=supplier.name,
		items=[
			{"item": items["laptop"].name, "qty": 10, "rate": 82000},
			{"item": items["monitor"].name, "qty": 20, "rate": 22500},
		],
	)
	_stock_entry(
		"Transfer",
		date=yesterday,
		source=warehouses["main"].name,
		target=warehouses["repair"].name,
		items=[
			{"item": items["laptop"].name, "qty": 5},
			{"item": items["dock"].name, "qty": 4},
		],
	)

	for date, warehouse, rows in [
		(
			today,
			warehouses["main"].name,
			[
				{"item": items["laptop"].name, "qty": 3, "selling_rate": 105000},
				{"item": items["monitor"].name, "qty": 8, "selling_rate": 30000},
				{"item": items["mouse"].name, "qty": 10, "selling_rate": 4000},
			],
		),
		(
			yesterday,
			warehouses["overflow"].name,
			[{"item": items["monitor"].name, "qty": 2, "selling_rate": 30000}],
		),
	]:
		sale = frappe.get_doc(
			{
				"doctype": "Sales Issue",
				"posting_date": date,
				"posting_time": frappe.utils.nowtime(),
				"customer": customer.name,
				"source_warehouse": warehouse,
				"items": rows,
			}
		).insert(ignore_permissions=True)
		sale.submit()

	count = frappe.get_doc(
		{
			"doctype": "Stock Count",
			"count_date": today,
			"count_time": frappe.utils.nowtime(),
			"warehouse": warehouses["main"].name,
			"reason": "Demo cycle count for voice-agent testing",
			"items": [
				{"item": items["laptop"].name, "counted_qty": 30},
				{"item": items["monitor"].name, "counted_qty": 60},
				{"item": items["dock"].name, "counted_qty": 24},
				{"item": items["mouse"].name, "counted_qty": 90},
			],
		}
	).insert(ignore_permissions=True)
	count.submit()

	frappe.db.commit()
	return {
		"created": True,
		"warehouses": [warehouse.name for warehouse in warehouses.values()],
		"items": [item.name for item in items.values()],
		"today": today,
		"yesterday": yesterday,
		"expected_questions": [
			"How many warehouses do we have?",
			"How many DEMO-LAPTOP-15 units do we have overall?",
			"What were today's sales?",
			"Are there any stock discrepancies?",
			"Which items are low in stock?",
		],
	}
