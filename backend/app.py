"""Local data API and explicitly budgeted, opt-in BAZE analysis commands."""
from contextlib import asynccontextmanager
from datetime import date as Date
from pathlib import Path
from typing import Annotated, Literal
from threading import Lock
from uuid import UUID
from backend.conversations import ConversationStore
from backend.task_tools import TaskManager, TaskToolRequest
from backend.course_tools import CourseManager, CourseRequest
from backend.planner import DatabaseSettings
from backend.schemas import RequestModel

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Path as ApiPath, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from starlette.middleware.trustedhost import TrustedHostMiddleware

from backend import analysis
from backend.ai import AIError, AnalysisAI, ChatRequest, Gateway, Settings
from backend.data import Dataset, load_dataset
from backend.planner import PlannerError
from backend.planner_api import router as planner_router
from backend.stt import router as stt_router
from backend.planner_api import briefing_result, get_weather
from backend.schemas import CompareRequest, DetailedRequest, PairsRequest, TimeseriesRequest, WindowsRequest, RegionAnalysisRequest
from scripts.prepare_app_data import fingerprint


DEFAULT_PACKAGE = Path(__file__).resolve().parents[1] / "data/processed/nervis_v1"
RegionPath = Annotated[str, ApiPath(pattern=r"^(?:[1-9]|1[0-9]|20)$")]
Orientation = Literal["Axial", "Coronal"]


def get_dataset(request: Request) -> Dataset:
    data = getattr(request.app.state, "dataset", None)
    if data is None:
        raise HTTPException(503, "Dataset is not loaded")
    return data


Data = Annotated[Dataset, Depends(get_dataset)]


def create_app(package_dir: Path = DEFAULT_PACKAGE, *, ai_service: AnalysisAI | None = None,
               planner_store=None, weather_service=None, conversation_store=None) -> FastAPI:
    package = Path(package_dir).resolve()
    ai_init_lock = Lock()

    @asynccontextmanager
    async def lifespan(application):
        try:
            application.state.dataset = load_dataset(package)
        except ValueError as exc:
            raise RuntimeError("App data package failed validation; run the offline verifier") from exc
        try:
            application.state.ai_service = ai_service
            application.state.planner_store = planner_store
            application.state.weather_service = weather_service
            application.state.conversation_store = conversation_store
            yield
        finally:
            del application.state.dataset
            del application.state.ai_service
            del application.state.planner_store
            del application.state.weather_service
            del application.state.conversation_store

    application = FastAPI(title="NERVIS Local API", version="0.2.0", lifespan=lifespan,
                          description="Local brain analysis, persistent planner and Korean microphone dictation. AI commands require explicit activation.",
                          redoc_url=None)
    application.add_middleware(CORSMiddleware,
                               allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
                               allow_methods=["GET", "POST", "PATCH", "DELETE"],
                               allow_headers=["Content-Type", "Idempotency-Key"])
    application.add_middleware(TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost"])
    application.include_router(planner_router)
    application.include_router(stt_router)

    @application.exception_handler(PlannerError)
    async def invalid_planner(request, exc):
        return JSONResponse(status_code=exc.status, content={"detail": exc.code})

    @application.exception_handler(RequestValidationError)
    async def invalid_request(request, exc):
        # Do not reflect complete input bodies or unexpected fields into responses.
        detail = [{k: error[k] for k in ("loc", "type", "msg")} for error in exc.errors()]
        return JSONResponse(status_code=422, content={"detail": detail})

    @application.exception_handler(ValueError)
    async def invalid_analysis(request, exc):
        return JSONResponse(status_code=422, content={"detail": str(exc)})

    @application.exception_handler(AIError)
    async def invalid_ai(request, exc):
        return JSONResponse(status_code=exc.status, content={"detail": exc.code})

    def ai_instance(request: Request):
        with ai_init_lock:
            if request.app.state.ai_service is None:
                try:
                    request.app.state.ai_service = AnalysisAI(Gateway(Settings.load()))
                except (ValueError, OSError):
                    raise HTTPException(503, "AI configuration is invalid") from None
            return request.app.state.ai_service

    @application.get("/api/ai/status", tags=["AI (opt-in)"])
    def ai_status(request: Request):
        service = ai_instance(request)
        remaining = service.gateway.remaining
        return {"enabled": service.gateway.settings.active and remaining != 0, "model": service.gateway.settings.model,
                "remaining_process_requests": remaining, "busy": service.busy.locked()}

    def conversations(request):
        with ai_init_lock:
            if request.app.state.conversation_store is None:
                request.app.state.conversation_store = ConversationStore(DatabaseSettings.load())
            return request.app.state.conversation_store

    @application.post('/api/conversations', tags=['conversation'])
    def create_conversation(body: RequestModel, request: Request):
        from backend.planner_api import check_origin
        check_origin(request)
        return conversations(request).create()

    @application.get('/api/conversations', tags=['conversation'])
    def list_conversations(request: Request, limit: Annotated[int, Query(ge=1,le=100)] = 50,
                           offset: Annotated[int, Query(ge=0,le=1000000)] = 0):
        return conversations(request).list(limit,offset)

    @application.get('/api/conversations/{session_id}', tags=['conversation'])
    def get_conversation(session_id: UUID, request: Request):
        return conversations(request).get(session_id)

    @application.post("/api/ai/chat", tags=["AI (opt-in)"])
    def ai_chat(body: ChatRequest, request: Request, data: Data, background_tasks: BackgroundTasks):
        origin = request.headers.get("origin")
        if origin and origin not in ("http://localhost:5173", "http://127.0.0.1:5173",
                                     "http://localhost:8000", "http://127.0.0.1:8000"):
            raise HTTPException(403, "AI origin is not allowed")
        service = ai_instance(request)
        services={
            'get_daily_briefing':lambda **p:briefing_result(request,**p),
            'get_weather':lambda date=None,location=None:{'kind':'weather',**get_weather(request).get(
                location,Date.fromisoformat(date) if date else None)}}
        if (body.session_id is None) != (body.request_id is None):
            raise HTTPException(422,'session_and_request_ids_required_together')
        if body.session_id is None:
            return service.run(data,body.command,body.context.model_dump(),services=services)
        store=conversations(request)
        def run_turn(history,state,conn):
            manager=TaskManager(store,conn,state.get('planner'))
            task_services={**services,'manage_tasks':lambda **p:manager.execute(TaskToolRequest.model_validate(p)),
                           'list_tasks':manager.list_tasks,
                           'register_courses':lambda **p:CourseManager(store,conn,manager.state).execute(CourseRequest.model_validate(p))}
            result=service.run(data,body.command,body.context.model_dump(),services=task_services,
                               history=history,session_state={**{k:v for k,v in state.items() if k in ('context','last_result_refs','last_assistant_message')},'planner':manager.public_state()})
            result['planner_state']=manager.state
            return result
        result=store.chat(body.session_id,body.request_id,body.command,body.context.model_dump(),run_turn)
        background_tasks.add_task(store.generate_title,body.session_id,service.generate_title)
        return result

    @application.get("/api/health", tags=["dataset"])
    def health(data: Data):
        return {"status": "ok", "dataset_version": data.dataset_version}

    @application.get("/api/dataset", tags=["dataset"])
    def summary(data: Data):
        return analysis.get_dataset_summary(data)

    @application.get("/api/regions", tags=["dataset"])
    def regions(data: Data):
        return {"dataset_version": data.dataset_version,
                "regions": [analysis.get_region_info(data, i)["region"] for i in range(1, 21)]}

    @application.get("/api/regions/{region_id}", tags=["dataset"])
    def region(region_id: RegionPath, data: Data):
        return analysis.get_region_info(data, int(region_id))

    @application.get("/api/regions/{region_id}/slices", tags=["dataset"])
    def region_slices(region_id: RegionPath, data: Data, orientation: Orientation = "Axial"):
        return analysis.get_region_slices(data, int(region_id), orientation)

    @application.post("/api/analysis/timeseries", tags=["analysis"])
    def timeseries(body: TimeseriesRequest, data: Data):
        return analysis.get_timeseries(data, **body.model_dump())

    @application.post("/api/analysis/compare", tags=["analysis"])
    def compare(body: CompareRequest, data: Data):
        return analysis.compare_regions(data, **body.model_dump())

    @application.post("/api/analysis/pairs", tags=["analysis"])
    def pairs(body: PairsRequest, data: Data):
        return analysis.find_similar_pairs(data, **body.model_dump())

    @application.post("/api/analysis/windows", tags=["analysis"])
    def windows(body: WindowsRequest, data: Data):
        return analysis.analyze_pair_over_windows(data, **body.model_dump())

    @application.post("/api/analysis/detailed", tags=["analysis"])
    def detailed(body: DetailedRequest, data: Data):
        return analysis.analyze_regions_detailed(data, **body.model_dump())

    @application.post("/api/analysis/region", tags=["analysis"])
    def analyze_region(body: RegionAnalysisRequest, data: Data):
        return analysis.analyze_region(data, **body.model_dump())

    @application.get("/api/slices/{orientation}/{slice_index}/{kind}", tags=["images"])
    def image(orientation: Orientation, slice_index: Annotated[int, ApiPath(ge=0, le=999)],
              kind: Literal["t1", "mask"], data: Data):
        record = next((r for r in data.slice_index["slices"]
                       if r["orientation"] == orientation and r["slice_index"] == slice_index), None)
        if record is None:
            raise HTTPException(404, "Slice not found")
        name = record["t1_path" if kind == "t1" else "mask_path"]
        path = (package / name).resolve()
        if not path.is_relative_to(package) or not path.is_file():
            raise HTTPException(409, "Package image is missing or outside the package")
        if fingerprint(path) != data.manifest["files"][name]:
            raise HTTPException(409, "Package image changed; verify data and restart the server")
        return FileResponse(path, media_type="image/png", headers={"Cache-Control": "no-store"})

    return application


app = create_app()
