frappe.query_reports["Stock Discrepancy"] = {
    filters: [
        { fieldname: "warehouse", label: "Warehouse", fieldtype: "Link", options: "Warehouse" },
        { fieldname: "counted_by", label: "Counted By", fieldtype: "Link", options: "User" }
    ]
};
