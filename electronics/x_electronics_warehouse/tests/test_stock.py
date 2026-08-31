import frappe
from frappe.tests import IntegrationTestCase

from electronics.x_electronics_warehouse.stock import get_balance


class TestStock(IntegrationTestCase):
    def make_item(self):
        code = "TEST-ITEM-" + frappe.generate_hash(length=6).upper()

        return frappe.get_doc(
            {
                "doctype": "Item",
                "item_code": code,
                "item_name": "Test Item",
                "unit": "NOS",
                "valuation_method": "Moving Average",
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
                    }
                ],
            }
        )
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

