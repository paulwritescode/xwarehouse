frappe.query_reports["Stock Balance"] = {
    filters: [
        {
            fieldname: "to_date",
            label: "To Date",
            fieldtype: "Date",
            default: frappe.datetime.get_today(),
            reqd: 1
        },
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