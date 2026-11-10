frappe.pages["warehouse-dashboard"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({ parent: wrapper, title: "Warehouse control room", single_column: true });
	$(wrapper).find(".layout-main-section").html(`
		<div class="xw-desk-page"><div class="xw-desk-shell">
			<aside class="xw-desk-sidebar">
				<div class="xw-desk-brand"><span class="xw-brand-mark">X</span><span><strong>XWarehouse</strong><small>Operations</small></span></div>
				<nav aria-label="Warehouse navigation">
					<div class="xw-nav-label">Control room</div>
					<a class="xw-nav-link is-active" href="/app/warehouse-dashboard"><span>◈</span> Overview</a>
					<a class="xw-nav-link" href="/app/warehouse"><span>⌂</span> Warehouses</a>
					<a class="xw-nav-link" href="/app/item"><span>□</span> Items</a>
					<div class="xw-nav-label">Movement</div>
					<a class="xw-nav-link" href="/app/stock-entry"><span>↔</span> Stock entries</a>
					<a class="xw-nav-link" href="/app/purchase-receipt"><span>↓</span> Receipts</a>
					<a class="xw-nav-link" href="/app/sales-issue"><span>↑</span> Sales issues</a>
					<div class="xw-nav-label">Review</div>
					<a class="xw-nav-link" href="/app/low-stock"><span>!</span> Low stock</a>
					<a class="xw-nav-link" href="/app/stock-count"><span>✓</span> Stock counts</a>
					<a class="xw-nav-link" href="/app/warehouse-call"><span>◉</span> Call centre</a>
				</nav>
				<div class="xw-sidebar-foot"><span class="xw-live-dot"></span><span>Frappe workspace<br><small>Connected to XWarehouse</small></span></div>
			</aside>
			<main class="xw-desk-main">
				<div class="xw-desk-heading"><div><p class="xw-kicker">OPERATIONS / OVERVIEW</p><h1>Warehouse control room</h1><p class="xw-heading-note">A clear view of stock, movement and the work that needs attention.</p></div><div class="xw-heading-actions"><span class="xw-date-label" data-today></span><a class="xw-outline-button" href="/app/warehouse-call">Open call centre <span>→</span></a></div></div>
				<div class="xw-metric-grid" data-metrics></div>
				<div class="xw-content-grid"><section class="xw-panel xw-panel-large"><div class="xw-panel-heading"><div><p class="xw-kicker">STOCK HEALTH</p><h2>Low stock watchlist</h2></div><a href="/app/low-stock">View report →</a></div><div data-low-stock></div></section><section class="xw-panel"><div class="xw-panel-heading"><div><p class="xw-kicker">REVIEW QUEUE</p><h2>Recorded variances</h2></div><a href="/app/stock-discrepancy">All →</a></div><div data-discrepancies></div></section></div>
				<section class="xw-panel xw-quick-panel"><div class="xw-panel-heading"><div><p class="xw-kicker">SHORTCUTS</p><h2>Keep work moving</h2></div></div><div class="xw-shortcuts"><a href="/app/purchase-receipt"><strong>Receive stock</strong><span>Record incoming items →</span></a><a href="/app/stock-entry"><strong>Move stock</strong><span>Transfer between warehouses →</span></a><a href="/app/sales-issue"><strong>Issue a sale</strong><span>Reduce stock with context →</span></a><a href="/app/stock-count"><strong>Count stock</strong><span>Record a physical check →</span></a></div></section>
			</main>
		</div></div>
	`);
	page.set_secondary_action("Refresh", () => load_dashboard(wrapper), "refresh");
	$(wrapper).find("[data-today]").text(format_today());
	load_dashboard(wrapper);
};

function escape_html(value) { return $("<div>").text(value == null ? "" : String(value)).html(); }
function format_number(value) { return new Intl.NumberFormat().format(Number(value || 0)); }
function format_today() { return new Intl.DateTimeFormat(undefined, { weekday: "short", day: "numeric", month: "short", year: "numeric" }).format(new Date()); }

function load_dashboard(wrapper) {
	const root = $(wrapper);
	root.find("[data-metrics], [data-low-stock], [data-discrepancies]").addClass("is-loading");
	Promise.all([
		frappe.call({ method: "electronics.x_electronics_warehouse.api.get_dashboard_summary" }),
		frappe.call({ method: "electronics.x_electronics_warehouse.api.get_low_stock" }),
		frappe.call({ method: "electronics.x_electronics_warehouse.api.get_stock_discrepancies" }),
	]).then(([summary_response, low_stock_response, discrepancy_response]) => {
		const summary = summary_response.message || {};
		const low_stock = low_stock_response.message || [];
		const discrepancies = (discrepancy_response.message || {}).discrepancies || [];
		root.find("[data-metrics]").html([
			metric_card("PHYSICAL WAREHOUSES", format_number(summary.warehouse_count), "active locations", "green"),
			metric_card("ITEMS CARRIED", format_number(summary.item_count), "catalogue items", "blue"),
			metric_card("UNITS ON HAND", format_number(summary.quantity), "across all locations", "orange"),
			metric_card("LOW STOCK LINES", format_number(summary.low_stock_count), summary.low_stock_count ? "needs review" : "all levels healthy", summary.low_stock_count ? "red" : "green"),
		].join(""));
		root.find("[data-low-stock]").html(render_low_stock(low_stock));
		root.find("[data-discrepancies]").html(render_discrepancies(discrepancies));
	}).catch(() => root.find("[data-metrics]").html('<div class="xw-error">Could not load the warehouse snapshot. Check your permissions and refresh.</div>')).finally(() => root.find("[data-metrics], [data-low-stock], [data-discrepancies]").removeClass("is-loading"));
}

function metric_card(label, value, detail, tone) { return `<article class="xw-metric-card xw-tone-${tone}"><span class="xw-metric-label">${label}</span><strong>${value}</strong><span class="xw-metric-detail">${detail}</span></article>`; }
function render_low_stock(rows) {
	if (!rows.length) return '<div class="xw-empty"><strong>Nothing is asking for attention.</strong><span>There are no item/location lines at or below their reorder level.</span></div>';
	return `<div class="xw-table-wrap"><table class="xw-table"><thead><tr><th>Item</th><th>Warehouse</th><th>On hand</th><th>Reorder at</th></tr></thead><tbody>${rows.slice(0, 8).map(row => `<tr><td><strong>${escape_html(row.item_code)}</strong><small>${escape_html(row.item_name || "")}</small></td><td>${escape_html(row.warehouse_name)}</td><td><span class="xw-status-pill xw-status-warn">${format_number(row.qty)} ${escape_html(row.unit || "")}</span></td><td>${format_number(row.reorder_level)}</td></tr>`).join("")}</tbody></table></div>`;
}
function render_discrepancies(rows) {
	if (!rows.length) return '<div class="xw-empty"><strong>No recorded variances.</strong><span>Stock counts are currently reconciled.</span></div>';
	return `<div class="xw-review-list">${rows.slice(0, 6).map(row => `<a href="/app/stock-count/${encodeURIComponent(row.stock_count)}"><span class="xw-review-icon">!</span><span><strong>${escape_html(row.item_code)}</strong><small>${escape_html(row.warehouse_name)} · ${escape_html(row.status)}</small></span><b>${row.variance > 0 ? "+" : ""}${format_number(row.variance)}</b></a>`).join("")}</div><p class="xw-panel-note">A discrepancy is a recorded variance, not proof of fraud.</p>`;
}
