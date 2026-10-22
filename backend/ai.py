"""Bounded BAZE function calling. Detailed data never returns to the model."""
from dataclasses import dataclass, field
import json
import math
import os
from pathlib import Path
import re
from threading import Lock
from typing import Annotated, Literal
from uuid import uuid4

from dotenv import dotenv_values
import httpx
from pydantic import Field, ValidationError

from backend import analysis
from backend.schemas import (RequestModel, RegionId, SampleRange, TimeseriesRequest,
                             CompareRequest, PairsRequest, WindowsRequest)


BASE_URL = "https://factchat-cloud.mindlogic.ai/v1/gateway"
ROOT = Path(__file__).resolve().parents[1]


class AIError(Exception):
    def __init__(self, code: str, status: int = 502):
        super().__init__(code)
        self.code, self.status = code, status


@dataclass(frozen=True)
class Settings:
    api_key: str = field(repr=False)
    model: str = ""
    max_requests: int = 0
    base_url: str = BASE_URL

    def __post_init__(self):
        if self.base_url.rstrip("/") != BASE_URL:
            raise ValueError("Only the documented BAZE gateway is allowed")
        if type(self.max_requests) is not int or not 0 <= self.max_requests <= 10:
            raise ValueError("AI request budget must be 0..10")
        if self.max_requests and (not self.api_key.strip() or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}", self.model)):
            raise ValueError("An explicit key and model are required to enable AI")

    @classmethod
    def load(cls, env_file: Path = ROOT / ".env", *, max_requests=None, model=None):
        values = {**dotenv_values(env_file, interpolate=False), **os.environ}
        return cls(values.get("BAZE_API_KEY") or "", model if model is not None else values.get("NERVIS_LLM_MODEL") or "",
                   int(values.get("NERVIS_AI_MAX_REQUESTS") or "0") if max_requests is None else max_requests,
                   values.get("NERVIS_BAZE_BASE_URL") or BASE_URL)


class Gateway:
    def __init__(self, settings: Settings, *, client: httpx.Client | None = None):
        self.settings, self.client = settings, client
        self.used = 0
        self.receipts = []
        self.lock = Lock()

    def send(self, endpoint: Literal["models/", "responses/"], payload=None):
        if endpoint not in ("models/", "responses/"):
            raise AIError("endpoint_not_allowed")
        with self.lock:
            if self.used >= self.settings.max_requests:
                raise AIError("ai_budget_exhausted_or_disabled", 503)
            self.used += 1  # Failed attempts count too; there is no retry or fallback.
            receipt = {"request": self.used, "endpoint": endpoint}
            self.receipts.append(receipt)
        owned = self.client is None
        client = self.client or httpx.Client(timeout=httpx.Timeout(30, connect=10), trust_env=False,
                                           follow_redirects=False)
        try:
            method = "GET" if endpoint == "models/" else "POST"
            with client.stream(method, BASE_URL + "/" + endpoint,
                               headers={"Authorization": "Bearer " + self.settings.api_key},
                               json=payload, follow_redirects=False) as response:
                receipt["http_status"] = response.status_code
                if response.status_code != 200:
                    raise AIError(f"gateway_http_{response.status_code}")
                content = bytearray()
                for chunk in response.iter_bytes():
                    content.extend(chunk)
                    if len(content) > 1_000_000:
                        raise AIError("gateway_response_too_large")
                result = json.loads(content)
                if not isinstance(result, dict):
                    raise AIError("gateway_invalid_json")
                receipt["usage"] = _usage(result)
                billing = result.get("billing")
                receipt["billing"] = {k: v for k, v in billing.items()
                    if k in ("cost_usd", "cost_krw", "deducted_credit")
                    and type(v) in (int, float) and math.isfinite(v) and v >= 0} if isinstance(billing, dict) else {}
                return result
        except (httpx.HTTPError, ValueError, UnicodeError):
            raise AIError("gateway_connection_or_json_error") from None
        finally:
            if owned:
                client.close()


class RegionRequest(RequestModel):
    region_id: RegionId


class SlicesRequest(RegionRequest):
    orientation: Literal["Axial", "Coronal"] = "Axial"


class CommandContext(SampleRange):
    selected_region_ids: Annotated[list[RegionId], Field(max_length=2)] = Field(default_factory=list)


class ChatRequest(RequestModel):
    command: Annotated[str, Field(min_length=1, max_length=600)]
    context: CommandContext = Field(default_factory=CommandContext)


TOOL_MODELS = {
    "get_dataset_summary": RequestModel, "get_region_info": RegionRequest,
    "get_timeseries": TimeseriesRequest, "compare_regions": CompareRequest,
    "find_similar_pairs": PairsRequest, "analyze_pair_over_windows": WindowsRequest,
    "get_region_slices": SlicesRequest,
}
TOOL_DESCRIPTIONS = {
    "get_dataset_summary": "Inspect dataset structure and units locally.",
    "get_region_info": "Inspect one region's structural measurements locally.",
    "get_timeseries": "Read selected regions' BOLD and z-score signals locally.",
    "compare_regions": "Compare two regions' signals, correlation and structure locally.",
    "find_similar_pairs": "Search correlation-ranked pairs; homologous means left/right counterparts.",
    "analyze_pair_over_windows": "Calculate correlations over sliding sample windows locally.",
    "get_region_slices": "Find registered MRI slices for a region locally.",
}
TOOLS = [{"type": "function", "name": name, "description": TOOL_DESCRIPTIONS[name],
          "parameters": model.model_json_schema(), "strict": False} for name, model in TOOL_MODELS.items()]
INSTRUCTIONS = """You are NERVIS, a Korean interface to local brain-data analysis tools.
Choose tools from the actual command, never simulate results. Left region IDs 1..10:
1 전전두피질, 2 운동·운동전피질, 3 체성감각피질, 4 후두정피질, 5 상측두피질,
6 중·하측두피질, 7 내측측두피질, 8 후두·시각피질, 9 대상피질, 10 섬엽피질.
Right counterparts have ID +10. A category comparison means its left/right pair.
Time is sample index, never seconds. No diagnosis, intelligence or personality inference.
Only status, not calculated results, will be returned to you. Never invent measurements,
rankings or scientific interpretation. Acknowledge completion briefly in Korean without
numbers; do not claim the screen was updated. No external tools or code execution.
At most one batch of 6 tools. If the command is ambiguous, ask for clarification.
"""


def _packet(value):
    if (value.get("status") != "completed" or not isinstance(value.get("output"), list)
            or not all(isinstance(item, dict) for item in value["output"])):
        raise AIError("gateway_incomplete_or_invalid_response")
    return value["output"]


def _acknowledgement(output):
    texts = []
    for item in output:
        if item.get("type") != "message":
            continue
        content = item.get("content")
        if not isinstance(content, list) or not all(isinstance(part, dict) for part in content):
            raise AIError("gateway_invalid_message")
        texts.extend(part["text"] for part in content if part.get("type") == "output_text" and isinstance(part.get("text"), str))
    return "\n".join(texts)[:2000]


def _usage(packet):
    value = packet.get("usage")
    return {k: v for k, v in value.items() if k in ("input_tokens", "output_tokens", "total_tokens")
            and type(v) is int and v >= 0} if isinstance(value, dict) else {}


class AnalysisAI:
    def __init__(self, gateway: Gateway):
        self.gateway, self.busy = gateway, Lock()

    def run(self, data, command: str, context: dict):
        body = ChatRequest(command=command, context=context)
        if not body.command.strip():
            raise AIError("empty_command", 422)
        if not self.busy.acquire(blocking=False):
            raise AIError("ai_request_in_progress", 409)
        before = self.gateway.used
        try:
            inputs = [{"role": "user", "content": json.dumps(
                {"command": body.command, "context": body.context.model_dump()}, ensure_ascii=False)}]
            request = {"model": self.gateway.settings.model, "instructions": INSTRUCTIONS,
                       "input": inputs, "tools": TOOLS, "parallel_tool_calls": False,
                       "max_output_tokens": 512, "store": False}
            first = self.gateway.send("responses/", request)
            output = _packet(first)
            if not all(isinstance(item, dict) for item in output):
                raise AIError("gateway_invalid_output")
            calls = [item for item in output if item.get("type") == "function_call"]
            if len(calls) > 6:
                raise AIError("too_many_tool_calls")
            acknowledgement = _acknowledgement(output)
            validated, ids = [], set()
            for item in calls:
                name, call_id, arguments = item.get("name"), item.get("call_id"), item.get("arguments")
                if not isinstance(name, str) or name not in TOOL_MODELS or not isinstance(call_id, str) or not 1 <= len(call_id) <= 200 or call_id in ids:
                    raise AIError("unknown_tool_or_duplicate_call")
                if not isinstance(arguments, str) or len(arguments) > 4000:
                    raise AIError("invalid_tool_arguments")
                try:
                    parameters = TOOL_MODELS[name].model_validate_json(arguments).model_dump()
                except ValidationError:
                    raise AIError("invalid_tool_arguments") from None
                ids.add(call_id); validated.append((name, parameters, call_id))
            results, feedback = [], []
            for name, parameters, call_id in validated:
                result = getattr(analysis, name)(data, **parameters)
                results.append({"result_id": uuid4().hex, "tool": name, "parameters": parameters, "data": result})
                feedback.append({"type": "function_call_output", "call_id": call_id,
                                 "output": json.dumps({"status": result["status"]})})
            status, warning = "ok", None
            usages = [_usage(first)]
            if feedback:
                # Only validated call metadata and status cross this boundary; no data/results.
                try:
                    second = self.gateway.send("responses/", {**request, "input": inputs + output + feedback,
                                                              "tool_choice": "none"})
                    final = _packet(second)
                    if any(item.get("type") == "function_call" for item in final):
                        raise AIError("unexpected_additional_tool_round")
                    acknowledgement = _acknowledgement(final)
                    usages.append(_usage(second))
                except AIError as exc:
                    status, acknowledgement, warning = "partial", None, exc.code
            return {"status": status, "model_acknowledgement": acknowledgement, "results": results,
                    "gateway_requests": self.gateway.used - before, "usage": usages,
                    "remaining_process_requests": self.gateway.settings.max_requests - self.gateway.used,
                    "warning": warning, "screen_applied": False}
        finally:
            self.busy.release()
