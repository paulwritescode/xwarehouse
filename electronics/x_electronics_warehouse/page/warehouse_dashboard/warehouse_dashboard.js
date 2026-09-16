frappe.pages["warehouse-dashboard"].on_page_load = function (wrapper) {
    const page = frappe.ui.make_app_page({
        parent: wrapper,
        title: "Warehouse Dashboard",
        single_column: true,
    });

    const body = $(wrapper).find(".layout-main-section");
    body.html(
        '<div class="warehouse-dashboard">' +
            '<div class="row dashboard-cards"></div>' +
            '<div class="dashboard-section"><h4>Low Stock</h4><div class="low-stock-table"></div></div>' +
        '</div>'
    );

    page.set_secondary_action("Refresh", () => load_dashboard(body), "refresh");
    load_dashboard(body);
};

function load_dashboard(body) {
    body.find(".dashboard-cards").html(
        '<div class="text-muted p-4">Loading dashboard...</div>'
    );

    frappe.call({
        method: "electronics.x_electronics_warehouse.api.get_dashboard_summary",
        callback: (response) => {
            const data = response.message || {};
            const cards = [
                ["Stock Value", format_currency(data.stock_value || 0)],
                ["Quantity", flt(data.quantity || 0)],
                ["Items", data.item_count || 0],
                ["Warehouses", data.warehouse_count || 0],
                ["Low Stock", data.low_stock_count || 0],
            ];
            body.find(".dashboard-cards").html(
                cards.map((card) =>
                    '<div class="col-sm-6 col-md-2"><div class="card mb-4"><div class="card-body">' +
                    '<div class="text-muted">' + card[0] + '</div>' +
                    '<div class="h3 mb-0">' + card[1] + '</div>' +
                    '</div></div></div>'
                ).join("")
            );
        },
    });

    frappe.call({
        method: "electronics.x_electronics_warehouse.api.get_low_stock",
        callback: (response) => {
            const rows = response.message || [];
            body.find(".low-stock-table").html(
                rows.length
                    ? '<table class="table table-bordered"><thead><tr><th>Item</th><th>Warehouse</th><th>Quantity</th><th>Reorder Level</th></tr></thead><tbody>' +
                      rows.map((row) =>
                          '<tr><td>' + row.item_code + '</td><td>' + row.warehouse_name +
                          '</td><td>' + row.qty + '</td><td>' + row.reorder_level + '</td></tr>'
                      ).join("") +
                      '</tbody></table>'
                    : '<div class="text-muted">No low-stock items.</div>'
            );
        },
    });
}
