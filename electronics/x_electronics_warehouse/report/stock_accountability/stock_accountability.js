frappe.query_reports["Stock Accountability"] = {
    filters: [
        { fieldname: "checked_out_to", label: "Checked Out To", fieldtype: "Link", options: "User" },
        { fieldname: "warehouse", label: "Warehouse", fieldtype: "Link", options: "Warehouse" },
        { fieldname: "only_outstanding", label: "Only Outstanding", fieldtype: "Check", default: 1 }
    ]
};
