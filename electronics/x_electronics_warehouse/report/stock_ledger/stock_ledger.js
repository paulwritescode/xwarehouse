frappe.query_reports["Stock Ledger"] = {
    filters: [
        {
            fieldname: "item",
            label: "Item",
            fieldtype: "Link",
            options: "Item"
        },
        {
            fieldname: "warehouse",
            label: "Warehouse",
            fieldtype: "Link",
            options: "Warehouse"
        }
    ]
};