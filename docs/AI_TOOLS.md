# AI analysis tools and result explanations

## Current implementation — 2026-10-23

Commands reach POST `/api/ai/chat`. The first Responses request selects allowlisted tools,
Python calculates locally, and a second request explains approved summary facts in Korean.
`answer` and `used_fact_ids` are parsed from that final response; no `memory_update`, DB,
conversation history, RAG, STT/TTS or deployment is included. The local HTTP field
`model_acknowledgement` retains its name for compatibility but now contains the explanation.
A model clarification without tools remains plain text. No screen-completion claim is inferred.

Nine strict tools: get_dataset_summary, get_region_info, analyze_region, get_timeseries, compare_regions,
find_similar_pairs, analyze_pair_over_windows, get_region_slices, analyze_regions_detailed.
All arguments in a batch (maximum six calls) are validated before execution. Additional
rounds, arbitrary paths/code/tools and automatic retries/model fallback are forbidden.

Basic comparison returns range-specific correlation plus thickness/volume and their differences.
Detailed analysis adds both correlations, relative structure differences, raw/global-z-score
mean/std/IQR/RMS/adjacent-change RMS, moving-window correlations, all/homologous rankings,
selection-related top pairs, major selected/all-region sample points, autocorrelation, Hann and
boxcar spectral peaks, and both raw-centered and within-range-standardized all-20-region PCA.
All modules run within the requested sample interval. Structure is fixed independently of it.
Local POST `/api/analysis/detailed` exposes the same compound function without AI calls.

Single-region analysis uses `analyze_region(region_id, start, end)` and local POST
`/api/analysis/region`: structural measurements, raw/global-z-score statistics and up to
five major deviation/change samples. The comparison-shaped display payload contains
only the requested region and is local-only; no partner/correlation is invented.
The explanation boundary forwards only approved structure/statistics/major-point/condition
summaries. Single-region ID analysis is the default for analysis requests; structure-only
questions may use get_region_info. Explicit global highest-correlation searches use all
190 candidate pairs and default to returning the top one, without requiring a selection.
Live model tool-choice/response quality after this revision remains unverified.

Conversation continuity and DB work were deferred by the user. ChatRequest retains only
the current command and selected IDs/range; no history/session-memory fields were added.

Missing/constant metrics return unavailable with reasons, not invented zeros. Spectrum peaks
require at least eight samples. Autocorrelation retains at least three overlapping samples.
Spectral units are cycles/sample, never Hz; actual sample interval is unknown. PCA uses all20
regions in the requested interval, not an anatomical network. The first three PCA components
have selected/top loadings; all explained-variance ratios remain local. Major points are up to
five peaks spaced at least10 samples apart; changes refer to the later sample. Relative
structure difference is 100*(b-a)/((a+b)/2), with null for a zero denominator. These are
strictly descriptive statistics, not clinical or cognitive inferences.

## Outbound data boundary

The user approved sending analysis summary metrics to BAZE for explanations.
`backend/ai_facts.py` constructs bounded facts: region IDs/Korean names/hemispheres,
validated arguments, dataset version, status, units/normalization, correlation, structural
measurements/differences, signal distribution, window extrema, up to five ranked pairs,
major points, selected autocorrelation lags1/5/10/20, spectral peaks and PCA summaries.
The final prompt asks for target/range → main results → meaning, avoiding completion-only
phrasing and promises to display results. It requests3–5 plain-Korean sentences for basic
results: overall finding first, everyday meaning second, then a few essential supporting
details. Detailed requests use a few short paragraphs of main findings rather than every
metric/ranked sample; full values remain in the calculation tab. Unavoidable terms are
explained. Signal magnitude must not be equated with more activity or better ability.
Missing conditions are explained when material. This wording revision has not been
verified with a live model request.

Never transmit MRI/mask pixels, file paths, raw/full signal arrays, file hashes, actual
credentials or identifying information. Complete calculations remain on local HTTP only.
Commands are for instructions, not pasted private files/keys. This is not an automatic
personal-data classifier. `store:false` is requested; provider retention is not verified.

Explanation JSON must contain only answer and used_fact_ids. References must be unique,
exist in the supplied fact map, and be nonempty when facts are available. Invalid output
returns status:partial with intact local calculations and no automatic repeat. Reference
validation does not prove every natural-language interpretation is correct. Actual model
quality and this new output protocol still need a separately approved small live test.

## Activation, limits and status

`NERVIS_AI_ENABLED=false` disables the app. Setting it to true explicitly enables ordinary
user commands without a total call-count cap. The real .env is not edited by this change.
If AI_ENABLED is absent, the old MAX_REQUESTS=0..10 behavior remains; legacy0 still means
off, never unlimited. Explicit developer-test max_requests overrides remain bounded even
when the app is enabled. `.env.example` explains migration and restart/OS override behavior.

One command uses at most two requests: routing max_output_tokens512, explanation1200.
Input is billed as well; there is no guaranteed currency cap. No retries, redirects,
proxy discovery, fallback, model discovery or account-balance polling. Destination is
fixed to the documented BAZE Gateway. Failed attempts count against bounded tests.
One command runs at a time (409 on concurrency), no queue. Timeout does not prove no charge.
Only numeric usage/billing receipts are retained; secrets/provider error bodies are not logged.

GET `/api/ai/status` is local only, not authentication or credit verification. Remaining
attempts are null in ordinary unlimited app mode. Auth errors, explicit credit errors,
rate limits and network errors have separate UI messages. A429 alone never proves no credit.
Previous real test allowances are exhausted; restarting or enabling the app does not authorize
agent-issued paid tests. Current development validation uses synthetic tests/MockTransport.

## Frontend behavior

Current selected IDs and actual displayed sample range are sent with commands. Before any
analysis there is no selected target (IDs[]); the model must ask when unspecified. An AI or
manual selection becomes the current focus. Moving-window selection updates the range;
playback cursor alone does not. There is no past-turn or old-ranking recall.

The analysis left panel has MRI/response/calculation tabs under the orb. The docked response
has no close button and contains only narrative/status, while calculations have their own tab.
Switching tabs retains results without another model request. Detailed items and multiple tool
results are selected one at a time; structure/statistics/windows use compact tables. Calculation
conditions are collapsed. Ranking pair selection remains local. The brain and signal share one
central frame. The home processing window is unchanged. Header and orb
share STANDBY/PROCESSING/ANALYZING/ERROR/PAUSED, with blue shell, orange processing core,
cyan applying core and red error core; reduced motion suppresses pulse/rotation. Audio preview
remains labelled preview; no fake STT/TTS state. Stop is square, actual correlation range is
explicit, and the generic fixed disclaimer/developer refresh button are removed.

Duplicate/Enter/IME guards, failed-draft and local-result preservation, 70s timeout and local
scene retry are maintained. Screen readiness still includes MRI/model/camera settlement.

## Historical verification checkpoints (older scopes)

## Verification and live status (2026-10-22)

`tests/test_ai.py` uses synthetic packages and httpx MockTransport to check real local calculations, status-only feedback, strict arguments, duplicate/excess calls, budgets, no retry, invalid model responses and partial results. `tests/test_ai_api.py` checks the FastAPI route, disabled state, request validation, origin checks and busy rejection. No test needs the real key or supplied data.

Explicit live checks are `python -m scripts.check_baze models` (one request) and `python -m scripts.check_baze smoke --model <approved-id>` (at most two requests, synthetic data only). Running either still requires approval; CLI flags do not create approval. The smoke checker never reads the original/processed package or modifies `.env`.

The user approved a model-list request and a conditional two-request test of `gpt-4.1-mini`/`gpt-5-mini`. The list request succeeded; neither candidate was present, so generation stopped. The actual list includes `gpt-5.4-mini`/`gpt-5.4-nano` and other models. The user subsequently chose to defer the proposed `gpt-5.4-mini` generation test. Total authenticated requests: one model listing; zero Responses requests. Actual tool-call/provider compatibility and generation cost remain unverified. No credit/balance/estimate endpoints were requested. Local reports are in `reports/ai-tools-20261022-01/`.

The current server remains disabled by default. The next step is an approved synthetic live tool test, followed by frontend text integration. Voice is a later step.


## Follow-up live result (2026-10-22)

After the initial deferral, the user selected gpt-5.4-mini and approved a separate run of at most5 Responses requests. That run used exactly5 and made no other authenticated requests. Three synthetic scenarios correctly selected tools/arguments: a named left/right comparison, a selected-context sliding-window analysis with explicit range, and a top-three homologous-pair search. The first two completed their status-only acknowledgement round. The last executed locally but did not request a final acknowledgement because the gateway budget had reached5; partial status is expected here.

Usage was5527 input +148 output =5675 tokens. Billing was absent, so actual credits deducted remain unknown; no balance/estimate lookup was made. This is evidence for retaining gpt-5.4-mini as the initial candidate for the implemented analysis tools, not proof of all system requests. History, weather/schedule, frontend and voice remain untested/unconnected. The actual .env and server budget remain unchanged (disabled by default). Records: `reports/ai-live-gpt54mini-20261022-01/`. This run's allowance is exhausted; further live requests require new approval.
# Current common briefing extension (2026-10-23)

See `BRIEFING_FLOW.md`: get_daily_briefing/get_weather now join analysis tools in the same two-request loop. Approved user-requested planner/weather summaries use explicit field selection, not entire DB rows. UI selects home cards vs analysis from actual typed results. A separately labelled pure-synthetic preview never calls external services or writes DB. Planner writes and voice remain unimplemented. This extension supersedes earlier brain-only/current-weather-placeholder notes below; live model routing quality has not been retested.

2026-10-24 conversation follow-up: optional session_id/request_id pair now provides persistent raw conversation history, grounded summary history and usage. Browser restoration/new conversation and retry safety are described in CONVERSATIONS.md. No automatic summary, RAG or planner writes; legacy no-history statements describe previous checkpoints.

2026-10-24 task-write follow-up: manage_tasks/list_tasks are now connected only in persistent session requests. Typed pending state, atomic batches and local receipt responses supersede previous task-read-only notes. See NATURAL_LANGUAGE_TASKS.md for the current contract, cancellation meaning and manual live checks. No actual course-write tool or live model verification was added.
# 2026-10-24 briefing task groups and titles

2026-10-24 course registration adds `register_courses` with typed partial drafts and same-session clarification/cancel, atomic courses/meetings registration and course-specific local receipts. See `NATURAL_LANGUAGE_COURSES.md`. It is an exclusive write call just like manage_tasks; no task/course mixing or course update/delete tools. Pending task/course drafts cannot overwrite each other.

Daily briefing now includes all incomplete tasks with task_group overdue/today/remaining; bounded summary facts carry the same labels/counts. See `BRIEFING_TASK_GROUPS.md`. Session title generation is a separate first-turn background request (80 output-token cap, no tools, no history mutation). It is not included in normal turn usage; its usage/time are stored separately in session state. It shares the configured gateway activation/request budget, never retries, and failure does not undo the successful conversation/task transaction. See `CONVERSATIONS.md`.
