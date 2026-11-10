"""XWarehouse voice agent with a fail-closed scope gate and read-only tool."""

import os

from dotenv import load_dotenv
from loguru import logger

from pipecat.frames.frames import LLMRunFrame, TTSSpeakFrame, TranscriptionFrame
from pipecat.evals.transport import EvalTransportParams
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.worker import PipelineParams, PipelineWorker
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.aggregators.llm_response_universal import (
	LLMContextAggregatorPair,
	LLMUserAggregatorParams,
)
from pipecat.runner.run import main
from pipecat.runner.types import RunnerArguments
from pipecat.runner.utils import create_transport
from pipecat.services.llm_service import FunctionCallParams
from pipecat.services.nvidia.llm import NvidiaLLMService
from pipecat.services.nvidia.stt import NvidiaSTTService
from pipecat.services.nvidia.tts import NvidiaTTSService, NvidiaTTSSynthesisMode
from pipecat.services.tts_service import TextAggregationMode
from pipecat.transports.base_transport import BaseTransport, TransportParams
from pipecat.transports.websocket.fastapi import FastAPIWebsocketParams
from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor

from frappe_client import FrappeClient, FrappeClientError
from guardrails import WAREHOUSE_SCOPE_MESSAGE, is_explicitly_out_of_scope


load_dotenv(override=True)


def required_env(name: str) -> str:
	value = os.getenv(name)
	if not value:
		raise RuntimeError(f"Missing required environment variable: {name}")
	return value


def daily_transport_params() -> TransportParams:
	"""Load Daily only when the Daily transport is explicitly requested."""
	from pipecat.transports.daily.transport import DailyParams

	return DailyParams(
		audio_in_enabled=True,
		audio_out_enabled=True,
	)


class WarehouseScopeGate(FrameProcessor):
	"""Prevent non-warehouse utterances from reaching the LLM."""

	async def process_frame(self, frame, direction):
		await super().process_frame(frame, direction)

		if direction == FrameDirection.DOWNSTREAM and isinstance(frame, TranscriptionFrame):
			if is_explicitly_out_of_scope(frame.text):
				logger.warning("Blocked out-of-scope warehouse query: {}", frame.text)
				await self.push_frame(
					TTSSpeakFrame(
						text=WAREHOUSE_SCOPE_MESSAGE,
						append_to_context=False,
					)
				)
				return

		await self.push_frame(frame, direction)


async def get_stock_balance(
	params: FunctionCallParams,
	item: str,
	warehouse: str,
):
	"""Read current stock for one item in one warehouse.

	Args:
		item: Exact Item identifier or item code in XWarehouse.
		warehouse: Exact Warehouse identifier.
	"""
	item = item.strip()
	warehouse = warehouse.strip()
	if not item or not warehouse or len(item) > 140 or len(warehouse) > 140:
		await params.result_callback({"ok": False, "error": "Invalid item or warehouse."})
		return

	client: FrappeClient = params.app_resources["frappe_client"]
	try:
		result = await client.get_stock_balance(item, warehouse)
		await params.result_callback({"ok": True, **result})
	except FrappeClientError:
		logger.exception("Stock balance tool failed")
		await params.result_callback(
			{
				"ok": False,
				"error": "Warehouse data is unavailable right now.",
			}
		)


async def get_warehouse_summary(params: FunctionCallParams):
	"""Count physical warehouses and list their names."""
	client: FrappeClient = params.app_resources["frappe_client"]
	try:
		await params.result_callback({"ok": True, **await client.get_warehouse_summary()})
	except FrappeClientError:
		logger.exception("Warehouse summary tool failed")
		await params.result_callback(
			{"ok": False, "error": "Warehouse data is unavailable right now."}
		)


async def get_item_stock_overall(params: FunctionCallParams, item: str):
	"""Read the total current quantity of an item across all warehouses.

	Args:
		item: Item code or item name. Use this for overall or total stock questions.
	"""
	item = item.strip()
	if not item or len(item) > 140:
		await params.result_callback({"ok": False, "error": "Invalid item."})
		return

	client: FrappeClient = params.app_resources["frappe_client"]
	try:
		await params.result_callback(
			{"ok": True, **await client.get_item_stock_overall(item)}
		)
	except FrappeClientError:
		logger.exception("Overall item stock tool failed")
		await params.result_callback(
			{"ok": False, "error": "Warehouse data is unavailable right now."}
		)


async def get_low_stock(
	params: FunctionCallParams,
	item: str | None = None,
	warehouse: str | None = None,
):
	"""Read items at or below their configured reorder level."""
	client: FrappeClient = params.app_resources["frappe_client"]
	try:
		rows = await client.get_low_stock(item, warehouse)
		await params.result_callback(
			{"ok": True, "count": len(rows), "items": rows[:20]}
		)
	except FrappeClientError:
		logger.exception("Low stock tool failed")
		await params.result_callback(
			{"ok": False, "error": "Warehouse data is unavailable right now."}
		)


async def get_sales_summary(
	params: FunctionCallParams,
	from_date: str | None = None,
	to_date: str | None = None,
	warehouse: str | None = None,
):
	"""Read submitted sales totals. With no dates, return today's sales."""
	client: FrappeClient = params.app_resources["frappe_client"]
	try:
		await params.result_callback(
			{"ok": True, **await client.get_sales_summary(from_date, to_date, warehouse)}
		)
	except FrappeClientError:
		logger.exception("Sales summary tool failed")
		await params.result_callback(
			{"ok": False, "error": "Sales data is unavailable right now."}
		)


async def get_stock_discrepancies(
	params: FunctionCallParams,
	warehouse: str | None = None,
):
	"""Read recorded stock-count discrepancies; do not label them as fraud."""
	client: FrappeClient = params.app_resources["frappe_client"]
	try:
		await params.result_callback(
			{"ok": True, **await client.get_stock_discrepancies(warehouse)}
		)
	except FrappeClientError:
		logger.exception("Stock discrepancy tool failed")
		await params.result_callback(
			{"ok": False, "error": "Discrepancy data is unavailable right now."}
		)


transport_params = {
	"eval": lambda: EvalTransportParams(
		audio_in_enabled=True,
		audio_out_enabled=True,
	),
	"webrtc": lambda: TransportParams(
		audio_in_enabled=True,
		audio_out_enabled=True,
	),
	"daily": daily_transport_params,
	"twilio": lambda: FastAPIWebsocketParams(
		audio_in_enabled=True,
		audio_out_enabled=True,
	),
}


async def bot(runner_args: RunnerArguments):
	"""Build one hosted-NVIDIA voice session."""
	transport: BaseTransport = await create_transport(runner_args, transport_params)

	api_key = required_env("NVIDIA_API_KEY")
	frappe_client = FrappeClient.from_env()
	if not frappe_client.configured:
		logger.warning(
			"FRAPPE_BASE_URL is not configured; warehouse tools will fail closed."
		)

	stt = NvidiaSTTService(
		api_key=api_key,
		settings=NvidiaSTTService.Settings(
			language=os.getenv("NVIDIA_STT_LANGUAGE", "en-US"),
			interim_results=True,
			automatic_punctuation=True,
		),
	)

	llm = NvidiaLLMService(
		api_key=api_key,
		base_url=os.getenv(
			"NVIDIA_LLM_BASE_URL",
			"https://integrate.api.nvidia.com/v1",
		),
		settings=NvidiaLLMService.Settings(
			model=os.getenv(
				"NVIDIA_LLM_MODEL",
				"nvidia/nemotron-3-super-120b-a12b",
			),
			system_instruction=(
				"/no_think\n"
				"You are the XWarehouse voice assistant. "
				"Answer briefly and naturally because your response is spoken aloud. "
				"Only discuss XWarehouse data. Use a registered warehouse tool for factual data. "
				"Never invent records, sales, stock, discrepancies, or fraud findings. "
				"Only use these read-only operations: count warehouses; read one-warehouse or overall item stock; "
				"read today's or date-range sales; read low-stock items; and read recorded stock-count discrepancies. "
				"For a question about fraud, explain that the system can report recorded discrepancies and unusual stock records, "
				"but cannot conclude fraud. Never create, edit, delete, approve, reject, transfer, receive, sell, or adjust stock. "
				"Use the overall-item tool when the user asks how much of an item exists across all warehouses. "
				"Use the warehouse-summary tool when the user asks how many warehouses there are. "
				"If the request is outside XWarehouse, politely refuse. "
				"Use short complete sentences with clear punctuation for natural speech. "
				"Never reveal analysis or internal reasoning."
			),
			temperature=0.2,
			max_completion_tokens=256,
			# NVIDIA-specific request fields must be nested in OpenAI's extra_body.
			extra={"extra_body": {"chat_template_kwargs": {"enable_thinking": False}}},
		),
	)

	tts = NvidiaTTSService(
		api_key=api_key,
		sample_rate=22050,
		text_aggregation_mode=TextAggregationMode.SENTENCE,
		append_trailing_space=True,
		settings=NvidiaTTSService.Settings(
			language=os.getenv("NVIDIA_TTS_LANGUAGE", "en-US"),
			voice=os.getenv(
				"NVIDIA_TTS_VOICE",
				"Magpie-Multilingual.EN-US.Aria",
			),
			synthesis_mode=NvidiaTTSSynthesisMode.STITCHED,
		),
	)

	context = LLMContext(
		tools=[
			get_warehouse_summary,
			get_stock_balance,
			get_item_stock_overall,
			get_low_stock,
			get_sales_summary,
			get_stock_discrepancies,
		]
	)
	user_aggregator, assistant_aggregator = LLMContextAggregatorPair(
		context,
		user_params=LLMUserAggregatorParams(
			vad_analyzer=SileroVADAnalyzer(),
		),
	)

	pipeline = Pipeline(
		[
			transport.input(),
			stt,
			WarehouseScopeGate(),
			user_aggregator,
			llm,
			tts,
			transport.output(),
			assistant_aggregator,
		]
	)

	worker = PipelineWorker(
		pipeline,
		app_resources={"frappe_client": frappe_client},
		params=PipelineParams(
			audio_in_sample_rate=16000,
			# NVIDIA Magpie synthesizes at 22.05 kHz; Pipecat resamples it
			# to the WebRTC-friendly 48 kHz output clock here.
			audio_out_sample_rate=48000,
			enable_metrics=True,
			enable_usage_metrics=True,
		),
		idle_timeout_secs=runner_args.pipeline_idle_timeout_secs,
	)

	@transport.event_handler("on_client_connected")
	async def on_client_connected(transport: BaseTransport, client):
		logger.info("XWarehouse voice client connected")
		context.add_message(
			{
				"role": "developer",
				"content": "Greet the user and ask how you can help with XWarehouse.",
			}
		)
		await worker.queue_frames([LLMRunFrame()])

	@transport.event_handler("on_client_disconnected")
	async def on_client_disconnected(transport: BaseTransport, client):
		logger.info("XWarehouse voice client disconnected")
		await worker.cancel()
		await frappe_client.close()

	from pipecat.workers.runner import WorkerRunner

	runner = WorkerRunner(handle_sigint=runner_args.handle_sigint)
	await runner.add_workers(worker)
	await runner.run()


if __name__ == "__main__":
	main()
