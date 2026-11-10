import frappe
from frappe.model.document import Document


class VoiceCallSession(Document):
	def validate(self):
		if self.session_type != "Daily Administrator Summary":
			frappe.throw("Only the daily administrator summary is configured currently.")
		if self.recipient != "Administrator":
			frappe.throw("The daily warehouse summary is currently addressed to Administrator.")
		if not self.public_token:
			self.public_token = frappe.generate_hash(length=32)

