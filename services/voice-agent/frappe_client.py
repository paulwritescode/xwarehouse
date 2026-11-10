"""Small, server-side client for the read-only XWarehouse Frappe API."""

from __future__ import annotations

import os
from typing import Any

import httpx


class FrappeClientError(RuntimeError):
	"""A safe-to-report Frappe integration error."""


class FrappeClient:
	def __init__(self, base_url: str | None, headers: dict[str, str]):
		self.base_url = base_url.rstrip("/") if base_url else None
		self._headers = headers
		self._http = httpx.AsyncClient(timeout=10.0)

	@classmethod
	def from_env(cls) -> "FrappeClient":
		base_url = os.getenv("FRAPPE_BASE_URL")
		api_key = os.getenv("FRAPPE_API_KEY")
		api_secret = os.getenv("FRAPPE_API_SECRET")

		if not base_url:
			return cls(None, {})
		if not api_key or not api_secret:
			raise RuntimeError(
				"FRAPPE_BASE_URL requires FRAPPE_API_KEY and FRAPPE_API_SECRET"
			)

		return cls(
			base_url,
			{"Authorization": f"token {api_key}:{api_secret}"},
		)

	@property
	def configured(self) -> bool:
		return self.base_url is not None

	async def _call(self, method: str, params: dict[str, Any] | None = None) -> Any:
		if not self.base_url:
			raise FrappeClientError("Frappe is not configured")

		endpoint = f"{self.base_url}/api/method/{method}"
		try:
			response = await self._http.get(
				endpoint,
				params=params or {},
				headers=self._headers,
			)
			response.raise_for_status()
			payload = response.json()
		except (httpx.HTTPError, ValueError) as exc:
			raise FrappeClientError("Frappe warehouse lookup failed") from exc

		if payload.get("exc"):
			raise FrappeClientError("Frappe rejected the warehouse lookup")
		return payload.get("message")

	async def get_stock_balance(self, item: str, warehouse: str) -> dict[str, Any]:
		balance = await self._call(
			"electronics.x_electronics_warehouse.api.get_stock_balance",
			{"item": item, "warehouse": warehouse},
		)
		return {"item": item, "warehouse": warehouse, "balance": balance}

	async def get_warehouse_summary(self) -> dict[str, Any]:
		return await self._call(
			"electronics.x_electronics_warehouse.api.get_warehouse_summary"
		)

	async def get_item_stock_overall(self, item: str) -> dict[str, Any]:
		return await self._call(
			"electronics.x_electronics_warehouse.api.get_item_stock_overall",
			{"item": item},
		)

	async def get_low_stock(
		self,
		item: str | None = None,
		warehouse: str | None = None,
	) -> list[dict[str, Any]]:
		return await self._call(
			"electronics.x_electronics_warehouse.api.get_low_stock",
			{"item": item, "warehouse": warehouse},
		)

	async def get_sales_summary(
		self,
		from_date: str | None = None,
		to_date: str | None = None,
		warehouse: str | None = None,
	) -> dict[str, Any]:
		return await self._call(
			"electronics.x_electronics_warehouse.api.get_sales_summary",
			{
				"from_date": from_date,
				"to_date": to_date,
				"warehouse": warehouse,
			},
		)

	async def get_stock_discrepancies(
		self,
		warehouse: str | None = None,
	) -> dict[str, Any]:
		return await self._call(
			"electronics.x_electronics_warehouse.api.get_stock_discrepancies",
			{"warehouse": warehouse},
		)

	async def close(self) -> None:
		await self._http.aclose()
