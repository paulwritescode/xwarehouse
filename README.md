# X Electronics Warehouse

A small warehouse-management application built with Frappe Framework. It is intentionally smaller than ERPNext and does not require ERPNext.

## Problem and solution

X Electronics needs to know how much stock is in each warehouse and which transactions produced that balance.

- Stock Entry is the document a warehouse user creates.
- Stock Ledger Entry is created automatically when a Stock Entry is submitted.
- Stock Balance shows the remaining quantity and value.
- Stock Ledger shows every movement in time order.

~~~mermaid
flowchart LR
    A[Define Item] --> B[Define Warehouse]
    B --> C[Create Stock Entry]
    C --> D{Purpose}
    D -->|Receipt| E[Add stock]
    D -->|Consume| F[Remove stock]
    D -->|Transfer| G[Move source to target]
    E --> H[Submit]
    F --> H
    G --> H
    H --> I[Create Stock Ledger Entry]
    I --> J[Stock Balance]
    I --> K[Stock Ledger]
~~~

Editable diagrams:

- [Stock flow explanation - Excalidraw](docs/stock_flow.excalidraw)
- [Application architecture - Draw.io](docs/architecture.drawio)

Open the first file in [Excalidraw](https://excalidraw.com/) and the second in [diagrams.net](https://app.diagrams.net/).

## DocTypes and tables

Every Frappe DocType becomes a MariaDB table, normally named tab plus the DocType name.

### Item (tabItem)

Defines a product. It does not store the current quantity.

| Label | Fieldname | Type | Purpose |
|---|---|---|---|
| Item Code | item_code | Data, mandatory, unique | Code such as HDMI-CABLE; also the document name |
| Item Name | item_name | Data, mandatory | Readable name such as HDMI Cable |
| Unit | unit | Data | Unit of measure; NOS means individual pieces |
| Valuation Method | valuation_method | Select | Currently Moving Average |

### Warehouse (tabWarehouse)

Defines a stock location and is a tree DocType.

| Label | Fieldname | Type | Purpose |
|---|---|---|---|
| Warehouse Name | warehouse_name | Data, mandatory, unique | Readable location name |
| Parent Warehouse | parent_warehouse | Link to Warehouse | Parent in the tree |
| Is Group | is_group | Check | Whether this node can contain children |
| Left / Right | lft, rgt | Int | Frappe tree bookkeeping fields |

The tree parent field is parent_warehouse; the naming rule is field:warehouse_name.

### Stock Entry Item (tabStock Entry Item)

This is a child table inside Stock Entry.

| Label | Fieldname | Type | Purpose |
|---|---|---|---|
| Item | item | Link to Item | Product moved |
| Quantity | qty | Float | Number of units |
| Rate | rate | Currency | Incoming price per unit |

### Stock Entry (tabStock Entry)

This is the user-facing, submittable transaction.

| Label | Fieldname | Type | Purpose |
|---|---|---|---|
| Posting Date | posting_date | Date | Transaction date |
| Posting Time | posting_time | Time | Transaction time |
| Purpose | purpose | Select | Receipt, Consume, or Transfer |
| Source Warehouse | source_warehouse | Link to Warehouse | Where stock leaves |
| Target Warehouse | target_warehouse | Link to Warehouse | Where stock enters |
| Items | items | Table: Stock Entry Item | Item rows |

| Purpose | Source | Target | Meaning |
|---|---|---|---|
| Receipt | Not required | Required | Add stock after buying or receiving goods |
| Consume | Required | Not required | Remove stock for a sale, internal use, or damage |
| Transfer | Required | Required | Move stock between two warehouses |

### Stock Ledger Entry (tabStock Ledger Entry)

This is a permanent, non-submittable history row. Users should not create it manually.

| Label | Fieldname | Type | Purpose |
|---|---|---|---|
| Posting Date | posting_date | Date | Movement date |
| Posting Time | posting_time | Time | Movement time |
| Item | item | Link to Item | Product |
| Warehouse | warehouse | Link to Warehouse | Affected location |
| Quantity Change | actual_qty | Float | Positive for addition, negative for removal |
| Incoming Rate | incoming_rate | Currency | Rate supplied for incoming stock |
| Valuation Rate | valuation_rate | Currency | Current moving-average rate |
| Quantity After Transaction | qty_after_transaction | Float | Balance after this movement |
| Stock Value | stock_value | Currency | Balance quantity multiplied by rate |
| Stock Entry | stock_entry | Link to Stock Entry | Source transaction |

## How users operate the system

### Receipt: buying or receiving stock

1. Open Stock Entry.
2. Set Purpose to Receipt.
3. Set Target Warehouse.
4. Add the Item, Quantity, and Rate.
5. Save and submit.

Example: receiving 10 HDMI cables at KES 1,000 creates 10 units worth KES 10,000. Submission automatically creates the ledger row.

### Consume: selling or using stock

This assignment has no separate Sales Invoice DocType, so a sale is represented by a Consume Stock Entry.

1. Set Purpose to Consume.
2. Set Source Warehouse.
3. Add the Item and Quantity.
4. Save and submit.

The system rejects a Consume when the requested quantity is greater than the available balance. Consuming 3 after receiving 10 leaves 7.

### Transfer: moving stock

1. Set Purpose to Transfer.
2. Set both Source and Target Warehouses.
3. Add the Item and Quantity.
4. Save and submit.

A transfer creates two ledger rows: a negative row in the source and a positive row in the target. It changes location, not the total business quantity.

## Moving Average valuation

For incoming stock:

~~~text
new quantity = old quantity + incoming quantity
new value = old value + (incoming quantity x incoming rate)
new rate = new value / new quantity
~~~

Example:

~~~text
10 x KES 100 = KES 1,000
10 x KES 200 = KES 2,000
20 units worth KES 3,000
Moving average rate = KES 3,000 / 20 = KES 150
~~~

When stock is consumed, value is reduced using the current rate. During a transfer, the source rate is carried to the target.

## Reports

Stock Balance answers “how much remains?” It displays Item Code, Item Name, Warehouse, Quantity In Stock, Moving Average Rate, and Stock Value up to the selected date.

Stock Ledger answers “what happened?” It displays date, time, item, warehouse, Quantity Change, rates, Balance After Transaction, Stock Value, and the source Stock Entry.

## Architecture

~~~mermaid
flowchart TB
    U[Warehouse User] --> D[Frappe Desk]
    D --> SE[Stock Entry]
    SE --> C[stock_entry.py: validate and on_submit]
    C --> S[stock.py: add_stock and get_balance]
    S --> L[(Stock Ledger Entry)]
    SE --> I[(Item)]
    SE --> W[(Warehouse)]
    L --> R1[Stock Balance report]
    L --> R2[Stock Ledger report]
    I --> DB[(MariaDB)]
    W --> DB
    L --> DB
~~~

The controller validates the transaction and calls the small functions in stock.py. The ledger is the source of truth; reports read it and join Item and Warehouse to show readable names.

## Installation

ERPNext is not needed.

~~~bash
cd /path/to/your/bench
bench get-app /path/to/electronics
bench --site xwarehouse install-app electronics
bench --site xwarehouse migrate
~~~

For local development:

~~~bash
cd /path/to/your/bench
bench start
~~~

## Testing

Business tests are in electronics/x_electronics_warehouse/tests/test_stock.py.

~~~bash
bench --site xwarehouse set-config allow_tests true
bench --site xwarehouse run-tests --app electronics
~~~

The tests cover Receipt, automatic ledger creation, Consume, Transfer, Moving Average valuation, and negative-stock protection.

## GitHub checklist

Commit the app source only:

~~~bash
cd /path/to/your/bench/apps/electronics
git init
git add .
git status
git commit -m "Build simple electronics warehouse system"
git branch -M main
git remote add origin https://github.com/YOUR-USERNAME/electronics.git
git push -u origin main
~~~

Do not commit the bench env/, site data under sites/, database data, passwords, API keys, Redis files, logs, or generated assets.

## License

MIT
