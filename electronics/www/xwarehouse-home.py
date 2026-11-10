import frappe

no_cache = 1


def get_context(context):
	context.no_cache = 1
	context.is_logged_in = frappe.session.user != "Guest"
	context.current_user = frappe.session.user
	context.dashboard_url = "/app/warehouse-dashboard"
	context.login_url = "/login?redirect-to=/app/warehouse-dashboard"
	context.call_url = "/app/warehouse-call"
	return context
