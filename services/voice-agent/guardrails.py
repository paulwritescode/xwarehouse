"""Deterministic guardrails for the XWarehouse voice agent."""

import re


WAREHOUSE_SCOPE_MESSAGE = (
	"I can only help with XWarehouse data, such as stock, sales, "
	"warehouse records, low stock, and discrepancies."
)

_WAREHOUSE_TERMS = (
	"warehouse",
	"inventory",
	"stock",
	"item",
	"sales",
	"sale",
	"receipt",
	"checkout",
	"return",
	"transfer",
	"ledger",
	"low stock",
	"balance",
	"count",
	"discrepanc",
	"anomal",
	"fraud",
	"record",
)

_OUT_OF_SCOPE_PATTERNS = (
	re.compile(r"\bexchange\s+rates?\b", re.IGNORECASE),
	re.compile(r"\bcurrency\b", re.IGNORECASE),
	re.compile(r"\b(?:weather|news|sports?|politics?)\b", re.IGNORECASE),
	re.compile(r"\bstock\s+market\b", re.IGNORECASE),
	re.compile(r"\b(?:write|debug|generate)\s+(?:code|script)\b", re.IGNORECASE),
)


def is_warehouse_query(text: str) -> bool:
	"""Return whether a user utterance is allowed into the warehouse agent."""
	normalized = " ".join(text.split()).strip()
	if not normalized:
		return False
	if is_explicitly_out_of_scope(normalized):
		return False
	return any(term in normalized.casefold() for term in _WAREHOUSE_TERMS)


def is_explicitly_out_of_scope(text: str) -> bool:
	"""Return whether text clearly requests a non-warehouse capability.

	Speech recognition can finalize one spoken sentence in several fragments.
	Unknown fragments therefore remain available to the warehouse-only LLM
	prompt, while clear off-topic requests are blocked before inference.
	"""
	normalized = " ".join(text.split()).strip()
	return bool(normalized) and any(
		pattern.search(normalized) for pattern in _OUT_OF_SCOPE_PATTERNS
	)
