import unittest

from guardrails import is_explicitly_out_of_scope, is_warehouse_query


class WarehouseScopeTests(unittest.TestCase):
	def test_allows_warehouse_questions(self):
		self.assertTrue(is_warehouse_query("How many warehouses do we have?"))
		self.assertTrue(is_warehouse_query("How much of this item do we have overall?"))
		self.assertTrue(is_warehouse_query("What are sales today?"))
		self.assertTrue(is_warehouse_query("Show me stock discrepancies."))

	def test_rejects_non_warehouse_questions(self):
		self.assertFalse(is_warehouse_query("What are the current exchange rates?"))
		self.assertFalse(is_warehouse_query("What is the weather today?"))
		self.assertTrue(is_explicitly_out_of_scope("What are the current exchange rates?"))

	def test_allows_speech_fragments_to_continue(self):
		self.assertFalse(is_explicitly_out_of_scope("Hello"))
		self.assertFalse(is_explicitly_out_of_scope("how are you"))

	def test_fails_closed_for_ambiguous_text(self):
		self.assertFalse(is_warehouse_query("Tell me something interesting."))


if __name__ == "__main__":
	unittest.main()
