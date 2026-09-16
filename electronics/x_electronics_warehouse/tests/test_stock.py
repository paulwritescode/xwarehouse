import frappe
from frappe.tests import IntegrationTestCase

from electronics.x_electronics_warehouse.stock import get_balance


class TestStock(IntegrationTestCase):
    def make_item(self, tracking_method="None"):
        code = "TEST-ITEM-" + frappe.generate_hash(length=6).upper()

        return frappe.get_doc(
            {
                "doctype": "Item",
                "item_code": code,
                "item_name": "Test Item",
                "unit": "NOS",
                "valuation_method": "Moving Average",
                "tracking_method": tracking_method,
            }
        ).insert(ignore_permissions=True)

    def make_warehouse(self, label):
        return frappe.get_doc(
            {
                "doctype": "Warehouse",
                "warehouse_name": f"Test {label} {frappe.generate_hash(length=6)}",
                "is_group": 0,
            }
        ).insert(ignore_permissions=True)

    def make_stock_entry(
        self,
        purpose,
        item,
        qty,
        rate=0,
        source_warehouse=None,
        target_warehouse=None,
        batch_no=None,
        serial_no=None,
    ):
        entry = frappe.get_doc(
            {
                "doctype": "Stock Entry",
                "posting_date": frappe.utils.today(),
                "posting_time": frappe.utils.nowtime(),
                "purpose": purpose,
                "source_warehouse": source_warehouse,
                "target_warehouse": target_warehouse,
                "items": [
                    {
                        "item": item.name,
                        "qty": qty,
                        "rate": rate,
                        "batch_no": batch_no,
                        "serial_no": serial_no,
                    }
                ],
            }
        )
        if purpose == "Transfer":
            entry.approval_status = "Approved"
        entry.insert(ignore_permissions=True)
        entry.submit()
        return entry

    def test_receipt_creates_ledger_entry(self):
        item = self.make_item()
        warehouse = self.make_warehouse("Receipt")

        entry = self.make_stock_entry(
            "Receipt",
            item,
            qty=10,
            rate=1000,
            target_warehouse=warehouse.name,
        )

        balance = get_balance(item.name, warehouse.name)
        ledger_count = frappe.db.count(
            "Stock Ledger Entry",
            {"stock_entry": entry.name},
        )

        self.assertEqual(balance["qty"], 10)
        self.assertEqual(balance["rate"], 1000)
        self.assertEqual(balance["value"], 10000)
        self.assertEqual(ledger_count, 1)

    def test_consume_reduces_stock(self):
        item = self.make_item()
        warehouse = self.make_warehouse("Consume")

        self.make_stock_entry(
            "Receipt",
            item,
            qty=10,
            rate=1000,
            target_warehouse=warehouse.name,
        )
        self.make_stock_entry(
            "Consume",
            item,
            qty=3,
            source_warehouse=warehouse.name,
        )

        balance = get_balance(item.name, warehouse.name)
        self.assertEqual(balance["qty"], 7)
        self.assertEqual(balance["value"], 7000)

    def test_transfer_moves_stock(self):
        item = self.make_item()
        source = self.make_warehouse("Source")
        target = self.make_warehouse("Target")

        self.make_stock_entry(
            "Receipt",
            item,
            qty=10,
            rate=1000,
            target_warehouse=source.name,
        )
        self.make_stock_entry(
            "Transfer",
            item,
            qty=4,
            source_warehouse=source.name,
            target_warehouse=target.name,
        )

        source_balance = get_balance(item.name, source.name)
        target_balance = get_balance(item.name, target.name)

        self.assertEqual(source_balance["qty"], 6)
        self.assertEqual(target_balance["qty"], 4)
        self.assertEqual(target_balance["rate"], 1000)

    def test_moving_average_rate(self):
        item = self.make_item()
        warehouse = self.make_warehouse("Average")

        self.make_stock_entry(
            "Receipt",
            item,
            qty=10,
            rate=100,
            target_warehouse=warehouse.name,
        )
        self.make_stock_entry(
            "Receipt",
            item,
            qty=10,
            rate=200,
            target_warehouse=warehouse.name,
        )

        balance = get_balance(item.name, warehouse.name)
        self.assertEqual(balance["qty"], 20)
        self.assertEqual(balance["rate"], 150)
        self.assertEqual(balance["value"], 3000)

    def test_consume_cannot_make_negative_stock(self):
        item = self.make_item()
        warehouse = self.make_warehouse("Negative")

        self.make_stock_entry(
            "Receipt",
            item,
            qty=2,
            rate=1000,
            target_warehouse=warehouse.name,
        )

        with self.assertRaises(frappe.ValidationError):
            self.make_stock_entry(
                "Consume",
                item,
                qty=3,
                source_warehouse=warehouse.name,
            )

    def test_receipt_requires_positive_quantity(self):
        item = self.make_item()
        warehouse = self.make_warehouse("Invalid Quantity")

        with self.assertRaises(frappe.ValidationError):
            self.make_stock_entry(
                "Receipt",
                item,
                qty=0,
                rate=1000,
                target_warehouse=warehouse.name,
            )

    def test_receipt_requires_positive_rate(self):
        item = self.make_item()
        warehouse = self.make_warehouse("Invalid Rate")

        with self.assertRaises(frappe.ValidationError):
            self.make_stock_entry(
                "Receipt",
                item,
                qty=1,
                rate=0,
                target_warehouse=warehouse.name,
            )

    def test_ledger_entry_cannot_be_created_manually(self):
        with self.assertRaises(frappe.ValidationError):
            frappe.get_doc(
                {
                    "doctype": "Stock Ledger Entry",
                    "posting_date": frappe.utils.today(),
                    "posting_time": frappe.utils.nowtime(),
                }
            ).insert(ignore_permissions=True)

    def test_cancelling_receipt_creates_reversal(self):
        item = self.make_item()
        warehouse = self.make_warehouse("Cancellation")
        entry = self.make_stock_entry(
            "Receipt",
            item,
            qty=5,
            rate=1000,
            target_warehouse=warehouse.name,
        )

        entry.cancel()

        balance = get_balance(item.name, warehouse.name)
        reversal_count = frappe.db.count(
            "Stock Ledger Entry",
            {"stock_entry": entry.name, "is_reversal": 1},
        )
        self.assertEqual(balance["qty"], 0)
        self.assertEqual(balance["value"], 0)
        self.assertEqual(reversal_count, 1)

    def test_cannot_cancel_when_later_movement_exists(self):
        item = self.make_item()
        warehouse = self.make_warehouse("Later Movement")
        entry = self.make_stock_entry(
            "Receipt",
            item,
            qty=5,
            rate=1000,
            target_warehouse=warehouse.name,
        )
        self.make_stock_entry(
            "Consume",
            item,
            qty=1,
            source_warehouse=warehouse.name,
        )

        with self.assertRaises(frappe.ValidationError):
            entry.cancel()

    def test_opening_stock_creates_a_normal_ledger_movement(self):
        item = self.make_item()
        warehouse = self.make_warehouse("Opening Stock")
        entry = self.make_stock_entry(
            "Opening Stock",
            item,
            qty=12,
            rate=750,
            target_warehouse=warehouse.name,
        )

        balance = get_balance(item.name, warehouse.name)
        self.assertEqual(balance["qty"], 12)
        self.assertEqual(balance["rate"], 750)
        self.assertEqual(balance["value"], 9000)
        self.assertEqual(
            frappe.db.count("Stock Ledger Entry", {"stock_entry": entry.name}),
            1,
        )

    def test_batch_tracking_keeps_batches_separate(self):
        item = self.make_item(tracking_method="Batch")
        warehouse = self.make_warehouse("Batch")
        self.make_stock_entry(
            "Receipt",
            item,
            qty=10,
            rate=100,
            target_warehouse=warehouse.name,
            batch_no="B-001",
        )
        self.make_stock_entry(
            "Receipt",
            item,
            qty=5,
            rate=200,
            target_warehouse=warehouse.name,
            batch_no="B-002",
        )

        batch_balance = get_balance(item.name, warehouse.name, batch_no="B-001")
        total_balance = get_balance(item.name, warehouse.name)
        self.assertEqual(batch_balance["qty"], 10)
        self.assertEqual(total_balance["qty"], 15)
        self.assertEqual(total_balance["value"], 2000)

    def test_serial_tracking_requires_one_identifier_per_row(self):
        item = self.make_item(tracking_method="Serial")
        warehouse = self.make_warehouse("Serial")
        self.make_stock_entry(
            "Receipt",
            item,
            qty=1,
            rate=500,
            target_warehouse=warehouse.name,
            serial_no="SN-001",
        )
        self.make_stock_entry(
            "Consume",
            item,
            qty=1,
            source_warehouse=warehouse.name,
            serial_no="SN-001",
        )

        balance = get_balance(item.name, warehouse.name, serial_no="SN-001")
        self.assertEqual(balance["qty"], 0)

    def test_transfer_requires_approval_before_submission(self):
        item = self.make_item()
        source = self.make_warehouse("Approval Source")
        target = self.make_warehouse("Approval Target")
        self.make_stock_entry(
            "Receipt", item, qty=2, rate=100, target_warehouse=source.name
        )

        transfer = frappe.get_doc(
            {
                "doctype": "Stock Entry",
                "posting_date": frappe.utils.today(),
                "posting_time": frappe.utils.nowtime(),
                "purpose": "Transfer",
                "source_warehouse": source.name,
                "target_warehouse": target.name,
                "items": [{"item": item.name, "qty": 1}],
            }
        ).insert(ignore_permissions=True)

        with self.assertRaises(frappe.ValidationError):
            transfer.submit()

        transfer.reload()
        transfer.approval_status = "Approved"
        transfer.submit()
        self.assertEqual(get_balance(item.name, target.name)["qty"], 1)

    def test_purchase_receipt_posts_stock_and_links_stock_entry(self):
        item = self.make_item()
        warehouse = self.make_warehouse("Purchase Receipt")
        supplier = frappe.get_doc(
            {
                "doctype": "Supplier",
                "supplier_code": "SUP-" + frappe.generate_hash(length=6).upper(),
                "supplier_name": "Test Supplier",
            }
        ).insert(ignore_permissions=True)
        receipt = frappe.get_doc(
            {
                "doctype": "Purchase Receipt",
                "posting_date": frappe.utils.today(),
                "posting_time": frappe.utils.nowtime(),
                "supplier": supplier.name,
                "target_warehouse": warehouse.name,
                "items": [{"item": item.name, "qty": 4, "rate": 250}],
            }
        ).insert(ignore_permissions=True)
        receipt.submit()

        self.assertTrue(receipt.stock_entry)
        self.assertEqual(get_balance(item.name, warehouse.name)["qty"], 4)

    def test_sales_issue_consumes_stock_and_links_stock_entry(self):
        item = self.make_item()
        warehouse = self.make_warehouse("Sales Issue")
        self.make_stock_entry("Receipt", item, qty=5, rate=100, target_warehouse=warehouse.name)
        customer = frappe.get_doc(
            {
                "doctype": "Customer",
                "customer_code": "CUS-" + frappe.generate_hash(length=6).upper(),
                "customer_name": "Test Customer",
            }
        ).insert(ignore_permissions=True)
        issue = frappe.get_doc(
            {
                "doctype": "Sales Issue",
                "posting_date": frappe.utils.today(),
                "posting_time": frappe.utils.nowtime(),
                "customer": customer.name,
                "source_warehouse": warehouse.name,
                "items": [{"item": item.name, "qty": 2, "selling_rate": 180}],
            }
        ).insert(ignore_permissions=True)
        issue.submit()

        self.assertTrue(issue.stock_entry)
        self.assertEqual(get_balance(item.name, warehouse.name)["qty"], 3)
        self.assertEqual(issue.total_revenue, 360)
        self.assertEqual(issue.total_cost, 200)
        self.assertEqual(issue.expected_profit, 160)

        from electronics.x_electronics_warehouse.report.sales_profit.sales_profit import execute

        _, profit_rows = execute({"customer": customer.name})
        self.assertTrue(any(row.sales_issue == issue.name for row in profit_rows))

    def test_stock_reports_and_dashboard_reflect_low_stock(self):
        item = self.make_item()
        item.reorder_level = 10
        item.reorder_qty = 20
        item.save(ignore_permissions=True)
        warehouse = self.make_warehouse("Reports")
        self.make_stock_entry(
            "Receipt", item, qty=4, rate=100, target_warehouse=warehouse.name
        )

        from electronics.x_electronics_warehouse.api import get_dashboard_summary
        from electronics.x_electronics_warehouse.report.low_stock.low_stock import (
            execute as execute_low_stock,
        )
        from electronics.x_electronics_warehouse.report.stock_balance.stock_balance import (
            execute as execute_balance,
        )

        _, balances = execute_balance({"item": item.name, "warehouse": warehouse.name})
        _, low_stock = execute_low_stock({"item": item.name, "warehouse": warehouse.name})
        summary = get_dashboard_summary()

        self.assertEqual(balances[0].qty, 4)
        self.assertEqual(low_stock[0].reorder_level, 10)
        self.assertGreaterEqual(summary["low_stock_count"], 1)

    def test_stock_checkout_tracks_custody_and_partial_return(self):
        item = self.make_item()
        warehouse = self.make_warehouse("Checkout")
        self.make_stock_entry(
            "Receipt", item, qty=5, rate=100, target_warehouse=warehouse.name
        )

        checkout = frappe.get_doc(
            {
                "doctype": "Stock Checkout",
                "checkout_date": frappe.utils.today(),
                "checkout_time": frappe.utils.nowtime(),
                "checked_out_to": "Administrator",
                "purpose": "Issue for installation",
                "warehouse": warehouse.name,
                "items": [{"item": item.name, "qty": 2}],
            }
        ).insert(ignore_permissions=True)
        checkout.submit()
        checkout.reload()

        self.assertEqual(checkout.status, "Checked Out")
        self.assertEqual(checkout.issued_by, "Administrator")
        self.assertEqual(checkout.items[0].outstanding_qty, 2)
        self.assertEqual(get_balance(item.name, warehouse.name)["qty"], 3)
        self.assertEqual(
            frappe.db.get_value("Stock Entry", checkout.stock_entry, "checked_out_to"),
            "Administrator",
        )

        returned = frappe.get_doc(
            {
                "doctype": "Stock Checkout Return",
                "return_date": frappe.utils.today(),
                "return_time": frappe.utils.nowtime(),
                "checkout": checkout.name,
                "items": [{"checkout_item": checkout.items[0].name, "qty": 1}],
            }
        ).insert(ignore_permissions=True)
        returned.submit()
        checkout.reload()

        self.assertEqual(checkout.status, "Partially Returned")
        self.assertEqual(checkout.items[0].returned_qty, 1)
        self.assertEqual(checkout.items[0].outstanding_qty, 1)
        self.assertEqual(get_balance(item.name, warehouse.name)["qty"], 4)

        from electronics.x_electronics_warehouse.report.stock_accountability.stock_accountability import execute

        _, custody_rows = execute({"only_outstanding": 1})
        self.assertEqual(custody_rows[0].outstanding_qty, 1)

    def test_stock_count_creates_attributed_adjustment_for_variance(self):
        item = self.make_item()
        warehouse = self.make_warehouse("Count")
        self.make_stock_entry(
            "Receipt", item, qty=5, rate=100, target_warehouse=warehouse.name
        )

        count = frappe.get_doc(
            {
                "doctype": "Stock Count",
                "count_date": frappe.utils.today(),
                "count_time": frappe.utils.nowtime(),
                "warehouse": warehouse.name,
                "reason": "Monthly count",
                "items": [{"item": item.name, "counted_qty": 3}],
            }
        ).insert(ignore_permissions=True)
        count.submit()
        count.reload()

        self.assertEqual(count.counted_by, "Administrator")
        self.assertEqual(count.items[0].system_qty, 5)
        self.assertEqual(count.items[0].variance, -2)
        self.assertEqual(count.items[0].variance_value, -200)
        self.assertEqual(count.has_discrepancy, 1)
        self.assertEqual(count.discrepancy_qty, 2)
        self.assertEqual(count.discrepancy_value, 200)
        self.assertEqual(count.status, "Adjusted")
        self.assertTrue(count.adjustment_stock_entry)
        self.assertEqual(get_balance(item.name, warehouse.name)["qty"], 3)

        from electronics.x_electronics_warehouse.report.stock_discrepancy.stock_discrepancy import execute

        _, discrepancy_rows = execute()
        self.assertTrue(any(row.stock_count == count.name for row in discrepancy_rows))

    def test_stock_count_without_variance_does_not_create_adjustment(self):
        item = self.make_item()
        warehouse = self.make_warehouse("No Variance")
        self.make_stock_entry(
            "Receipt", item, qty=5, rate=100, target_warehouse=warehouse.name
        )

        count = frappe.get_doc(
            {
                "doctype": "Stock Count",
                "count_date": frappe.utils.today(),
                "count_time": frappe.utils.nowtime(),
                "warehouse": warehouse.name,
                "items": [{"item": item.name, "counted_qty": 5}],
            }
        ).insert(ignore_permissions=True)
        count.submit()
        count.reload()

        self.assertEqual(count.status, "No Variance")
        self.assertFalse(count.adjustment_stock_entry)
        self.assertEqual(count.has_discrepancy, 0)
        self.assertEqual(count.discrepancy_qty, 0)
        self.assertEqual(count.discrepancy_value, 0)
        self.assertEqual(get_balance(item.name, warehouse.name)["qty"], 5)

        from electronics.x_electronics_warehouse.report.stock_discrepancy.stock_discrepancy import execute

        _, discrepancy_rows = execute()
        self.assertFalse(any(row.stock_count == count.name for row in discrepancy_rows))
