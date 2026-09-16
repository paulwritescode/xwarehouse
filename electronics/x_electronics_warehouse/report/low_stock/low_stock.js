frappe.query_reports["Low Stock"] = {
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
