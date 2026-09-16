frappe.ui.form.on("Stock Entry", {
    refresh(frm) {
        if (
            frm.doc.docstatus === 0 &&
            frm.doc.purpose === "Transfer" &&
            frm.doc.approval_status !== "Approved" &&
            (frappe.user.has_role("Warehouse Manager") || frappe.user.has_role("System Manager"))
        ) {
            frm.add_custom_button("Approve Transfer", () => {
                frappe.call({
                    method: "electronics.x_electronics_warehouse.api.approve_stock_entry",
                    args: { name: frm.doc.name },
                    callback: () => frm.reload_doc(),
                });
            });

            frm.add_custom_button("Reject Transfer", () => {
                frappe.call({
                    method: "electronics.x_electronics_warehouse.api.reject_stock_entry",
                    args: { name: frm.doc.name },
                    callback: () => frm.reload_doc(),
                });
            });
        }
    },
});
