# AI analysis tool connection

## Current text integration (2026-10-23)

Frontend text commands now reach `/api/ai/chat`. `GET /api/ai/status` reports only local model configuration, remaining process attempts and busy state; it never calls Gateway or validates live credentials. Budget0, busy or unknown status disables sending. Page loads never discover models or check account credits. Historical checkpoints below remain dated records.

Enter submits only from the textarea; Shift+Enter inserts a newline and IME composition does not submit. Messages are limited to600 characters. A synchronous duplicate guard covers requesting → applying → complete/error, including MRI/GLB loading and initial camera readiness. Controls reopen after completion. A70-second wait deadline never automatically repeats the model request; local status is rechecked. Failed drafts and completed local results survive errors. Scene-only retries make no model call and clear failed GLB cache entries.

All seven tools have local result displays. Pair/range/method/window arguments reach the stage; returned calculations are reused and missing display data uses local routes only. Ranking offers local pair selection. Single/multi-region and1~2-sample signals remain visible in the result inspector. MRI tools preserve a registered recommended slice. Model text is an acknowledgement, not interpretation of measurements it never received. Context includes only selected IDs/sample bounds, without history, images or local numeric results.

MockTransport browser QA uses fake credentials with real local functions/data and a visible test banner. It does not establish real gpt-5.4-mini frontend compatibility. The earlier5-call real allowance is exhausted; a new scoped approval is required before any new Gateway request. The real `.env` and disabled budget remain unchanged. STT/TTS, wake word, briefing, DB and full conversation history are outside this step.

## Implemented scope

`backend/ai.py` defines a bounded BAZE Responses client, seven strict analysis tools and the command loop. `POST /api/ai/chat` in `backend/app.py` accepts commands and explicit selection context. This step does not connect the frontend, microphone, TTS, wake word, daily briefing or conversational history. Restart the backend to load new routes.

The seven tools call existing `backend.analysis` functions: `get_dataset_summary`, `get_region_info`, `get_timeseries`, `compare_regions`, `find_similar_pairs`, `analyze_pair_over_windows`, `get_region_slices`. Names are allowlisted; arguments use strict Pydantic models. A single batch has at most six calls. All calls are validated before execution. Unknown tools, duplicate call IDs and extra arguments stop the batch.

## Data boundary

Only a command (up to 600 characters), generic region definitions, selected IDs/range and tool schemas are sent to the model. Commands are intended for instructions, not pasted datasets, credentials or identifying information; this is not a semantic personal-data classifier. No file attachment or arbitrary path/code tool exists.

Full analysis results return only to the local HTTP caller. The model receives its own preceding output plus matching `function_call_output` statuses (`ok`/`unavailable`), never measurements, signals, MRI, masks or dataset hashes. `store:false` requests that Responses state not be stored; it does not establish the provider's full retention policy. A model acknowledgement is not a scientific explanation of unseen results and is not proof the screen has updated. The HTTP response explicitly has `screen_applied:false`.

## Cost and execution limits

- Destination is fixed to `https://factchat-cloud.mindlogic.ai/v1/gateway`; another configured destination is rejected before sending a key. Redirects, environment proxy discovery and automatic retries are disabled.
- `NERVIS_AI_MAX_REQUESTS=0` by default. Configure a positive process budget only after approval. The hard maximum is 10. Failed/time-out attempts also consume this in-memory budget.
- A command has at most two model requests, each `max_output_tokens:512`. Input tokens are billed too; these are token/call limits, not a guaranteed credit/currency cap. There is no automatic model discovery, fallback or retry.
- Only one command executes at a time per service. Concurrent commands return409 rather than queueing.
- First-request failures stop without running analysis. If local analysis completes but the acknowledgement fails or requests more tools, return the local results with `status:partial`; do not execute another round.
- Numeric usage/billing fields are retained when the provider supplies them; error bodies, keys and headers are not logged. A timeout can still incur provider charges.
- The budget is per process and resets on restart; it is not a durable account-wide spending ledger. Use one local worker and do not restart to circumvent an approved budget.

The real `.env` is unchanged. `.env.example` documents the disabled default. `Settings.load` reads the local root `.env` without interpolation, with environment variables taking precedence. No key is sent to Vite or returned by the endpoint.

## Local HTTP format

```json
{
  "command": "전전두피질의 좌우를 비교해줘",
  "context": {"selected_region_ids": [1, 11], "start": 1, "end": 200}
}
```

Local response includes `results` (tool name, validated parameters, result handle and actual data), `model_acknowledgement`, per-response `usage`, consumed/remaining process requests and `warning`. No DB/session/result-retrieval API is added; handles identify results in this response only. Follow-up commands can provide selected context, but history and cross-request result recall are not implemented.

## Verification and live status (2026-10-22)

`tests/test_ai.py` uses synthetic packages and httpx MockTransport to check real local calculations, status-only feedback, strict arguments, duplicate/excess calls, budgets, no retry, invalid model responses and partial results. `tests/test_ai_api.py` checks the FastAPI route, disabled state, request validation, origin checks and busy rejection. No test needs the real key or supplied data.

Explicit live checks are `python -m scripts.check_baze models` (one request) and `python -m scripts.check_baze smoke --model <approved-id>` (at most two requests, synthetic data only). Running either still requires approval; CLI flags do not create approval. The smoke checker never reads the original/processed package or modifies `.env`.

The user approved a model-list request and a conditional two-request test of `gpt-4.1-mini`/`gpt-5-mini`. The list request succeeded; neither candidate was present, so generation stopped. The actual list includes `gpt-5.4-mini`/`gpt-5.4-nano` and other models. The user subsequently chose to defer the proposed `gpt-5.4-mini` generation test. Total authenticated requests: one model listing; zero Responses requests. Actual tool-call/provider compatibility and generation cost remain unverified. No credit/balance/estimate endpoints were requested. Local reports are in `reports/ai-tools-20261022-01/`.

The current server remains disabled by default. The next step is an approved synthetic live tool test, followed by frontend text integration. Voice is a later step.


## Follow-up live result (2026-10-22)

After the initial deferral, the user selected gpt-5.4-mini and approved a separate run of at most5 Responses requests. That run used exactly5 and made no other authenticated requests. Three synthetic scenarios correctly selected tools/arguments: a named left/right comparison, a selected-context sliding-window analysis with explicit range, and a top-three homologous-pair search. The first two completed their status-only acknowledgement round. The last executed locally but did not request a final acknowledgement because the gateway budget had reached5; partial status is expected here.

Usage was5527 input +148 output =5675 tokens. Billing was absent, so actual credits deducted remain unknown; no balance/estimate lookup was made. This is evidence for retaining gpt-5.4-mini as the initial candidate for the implemented analysis tools, not proof of all system requests. History, weather/schedule, frontend and voice remain untested/unconnected. The actual .env and server budget remain unchanged (disabled by default). Records: `reports/ai-live-gpt54mini-20261022-01/`. This run's allowance is exhausted; further live requests require new approval.
