frappe.query_reports["Sales Profit"] = {
    filters: [
        { fieldname: "customer", label: "Customer", fieldtype: "Link", options: "Customer" },
        { fieldname: "source_warehouse", label: "Warehouse", fieldtype: "Link", options: "Warehouse" },
        { fieldname: "from_date", label: "From Date", fieldtype: "Date" },
        { fieldname: "to_date", label: "To Date", fieldtype: "Date", default: frappe.datetime.get_today() }
    ]
};
