"""Strict HTTP inputs; calculations remain in backend.analysis."""
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


RegionId = Annotated[int, Field(ge=1, le=20)]
Sample = Annotated[int, Field(ge=1, le=200)]
Method = Literal["pearson", "spearman"]


class RequestModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class SampleRange(RequestModel):
    start: Sample = 1
    end: Sample = 200

    @model_validator(mode="after")
    def ordered_range(self) -> Self:
        if self.end < self.start:
            raise ValueError("end must be greater than or equal to start")
        return self


class TimeseriesRequest(SampleRange):
    region_ids: Annotated[list[RegionId], Field(min_length=1, max_length=20)]

    @model_validator(mode="after")
    def distinct_regions(self) -> Self:
        if len(set(self.region_ids)) != len(self.region_ids):
            raise ValueError("region_ids must be distinct")
        return self


class CompareRequest(SampleRange):
    region_a: RegionId
    region_b: RegionId
    method: Method = "pearson"

    @model_validator(mode="after")
    def valid_pair(self) -> Self:
        if self.region_a == self.region_b:
            raise ValueError("region_a and region_b must be distinct")
        if self.end-self.start+1 < 3:
            raise ValueError("Correlation requires at least 3 samples")
        return self


class RegionAnalysisRequest(SampleRange):
    region_id: RegionId


class PairsRequest(SampleRange):
    method: Method = "pearson"
    scope: Literal["all", "homologous"] = "all"
    order: Literal["ascending", "descending"] = "descending"
    limit: Annotated[int, Field(ge=1, le=190)] = 5

    @model_validator(mode="after")
    def valid_search(self) -> Self:
        if self.end-self.start+1 < 3:
            raise ValueError("Correlation requires at least 3 samples")
        if self.scope == "homologous" and self.limit > 10:
            raise ValueError("homologous scope contains only 10 pairs")
        return self


class WindowsRequest(CompareRequest):
    window: Annotated[int, Field(ge=3, le=200)] = 50
    step: Annotated[int, Field(ge=1, le=200)] = 10

    @model_validator(mode="after")
    def valid_windows(self) -> Self:
        count = self.end-self.start+1
        if self.window > count or self.step > count:
            raise ValueError("window and step must fit within the selected sample range")
        return self


class DetailedRequest(CompareRequest):
    window: Annotated[int | None, Field(ge=3, le=200)] = None
    step: Annotated[int | None, Field(ge=1, le=200)] = None

    @model_validator(mode="after")
    def valid_detail_window(self) -> Self:
        count = self.end-self.start+1
        if self.window is not None and self.window > count:
            raise ValueError("window must fit within the selected range")
        if self.step is not None and self.step > count:
            raise ValueError("step must fit within the selected range")
        return self
