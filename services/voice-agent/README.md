# XWarehouse voice agent

This is the first XWarehouse voice-agent slice. It uses:

- SmallWebRTC for local browser-to-agent audio
- NVIDIA hosted Nemotron Speech ASR
- NVIDIA hosted Nemotron LLM through the OpenAI-compatible endpoint
- NVIDIA hosted Nemotron Speech TTS

The service has a server-side Frappe adapter and read-only warehouse tools for
warehouse counts, item stock by warehouse or overall, sales totals, low stock,
and recorded stock-count discrepancies. The browser never receives the NVIDIA
or Frappe credentials.

## Run locally

From this directory:

```bash
cp .env.example .env
# Set NVIDIA_API_KEY, FRAPPE_BASE_URL, FRAPPE_API_KEY, and FRAPPE_API_SECRET.
uv sync
uv run python bot.py --transport webrtc
```

The Pipecat runner exposes its local WebRTC test UI at the address printed in
the terminal. The NVIDIA key stays in this server process; it must not be sent
to the browser.

## Initial model choices

```text
ASR: NVIDIA Nemotron ASR streaming
LLM: nvidia/nemotron-3-super-120b-a12b
TTS: Magpie-Multilingual.EN-US.Aria
```

The model names and voice settings remain environment-configurable while we
benchmark latency, transcription quality, tool-call reliability, and response
quality against warehouse questions.

## Guardrails and evals

The agent blocks clearly non-warehouse utterances before they reach the LLM and
fails closed when Frappe is not configured. Run the deterministic guardrail
tests from this directory with:

```bash
uv run python -m unittest discover -s tests -v
```

For Pipecat behavioral evals, start the eval transport in one terminal:

```bash
uv run python bot.py --transport eval
```

Then run the scenarios from another terminal:

```bash
pipecat eval run scenarios/warehouse_scope.yaml -v
```

If the CLI is not installed yet, install it separately so the agent's runtime
dependencies remain lightweight:

```bash
uv tool install "pipecat-ai[cli]"
```

## Demo records

The local `xwarehouse` site can be populated with a namespaced, idempotent demo
dataset. From the bench root, run:

```bash
bench --site xwarehouse execute electronics.x_electronics_warehouse.demo_data.seed_demo_data
```

This creates three demo warehouses, four demo items, submitted receipts, a
transfer, two sales issues, and a stock count containing known variances. The
voice agent remains read-only; it cannot create or modify these records.
