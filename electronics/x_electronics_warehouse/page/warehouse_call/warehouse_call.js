frappe.pages["warehouse-call"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: "Administrator call centre",
		single_column: true,
	});

	$(wrapper).find(".layout-main-section").html(
		'<div class="xw-call-page"><div id="xw-call-app"><div class="xw-call-loading">Loading call centre…</div></div></div>'
	);

	const load_call_client = () => {
		const script = document.createElement("script");
		script.src = "/assets/electronics/js/warehouse_call.js?v=20260930-7";
		document.body.appendChild(script);
	};
	const vue = document.createElement("script");
	vue.src = "/assets/frappe/node_modules/vue/dist/vue.global.prod.js";
	vue.onload = load_call_client;
	vue.onerror = () => {
		$(wrapper).find("#xw-call-app").html('<div class="xw-call-auth"><h1>Call centre unavailable</h1><p>The local Vue runtime could not be loaded from Frappe assets. Run <code>bench build --app electronics</code> and refresh.</p></div>');
	};
	document.body.appendChild(vue);

	page.set_secondary_action("Warehouse dashboard", () => frappe.set_route("warehouse-dashboard"), "dashboard");
};
