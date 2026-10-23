"""Local data API and explicitly budgeted, opt-in BAZE analysis commands."""
from contextlib import asynccontextmanager
from datetime import date as Date
from pathlib import Path
from typing import Annotated, Literal
from threading import Lock

from fastapi import Depends, FastAPI, HTTPException, Path as ApiPath, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from starlette.middleware.trustedhost import TrustedHostMiddleware

from backend import analysis
from backend.ai import AIError, AnalysisAI, ChatRequest, Gateway, Settings
from backend.data import Dataset, load_dataset
from backend.planner import PlannerError
from backend.planner_api import router as planner_router
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
               planner_store=None, weather_service=None) -> FastAPI:
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
            yield
        finally:
            del application.state.dataset
            del application.state.ai_service
            del application.state.planner_store
            del application.state.weather_service

    application = FastAPI(title="NERVIS Local API", version="0.2.0", lifespan=lifespan,
                          description="Local brain analysis and persistent planner. AI commands require explicit activation. No voice or login.",
                          redoc_url=None)
    application.add_middleware(CORSMiddleware,
                               allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
                               allow_methods=["GET", "POST", "PATCH", "DELETE"],
                               allow_headers=["Content-Type", "Idempotency-Key"])
    application.add_middleware(TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost"])
    application.include_router(planner_router)

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

    @application.post("/api/ai/chat", tags=["AI (opt-in)"])
    def ai_chat(body: ChatRequest, request: Request, data: Data):
        origin = request.headers.get("origin")
        if origin and origin not in ("http://localhost:5173", "http://127.0.0.1:5173",
                                     "http://localhost:8000", "http://127.0.0.1:8000"):
            raise HTTPException(403, "AI origin is not allowed")
        service = ai_instance(request)
        return service.run(data, body.command, body.context.model_dump(), services={
            'get_daily_briefing':lambda **p:briefing_result(request,**p),
            'get_weather':lambda date=None,location=None:{'kind':'weather',**get_weather(request).get(
                location,Date.fromisoformat(date) if date else None)}})

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
