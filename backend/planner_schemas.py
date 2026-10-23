"""Bounded planner inputs; relative dates are resolved before these contracts."""
from datetime import date, time
import re
from typing import Annotated, ClassVar, Literal

from pydantic import BeforeValidator, Field, model_validator
from backend.schemas import RequestModel


def parse_date(value):
    if type(value) is date:
        return value
    if isinstance(value, str) and re.fullmatch(r'\d{4}-\d{2}-\d{2}', value):
        return date.fromisoformat(value)
    raise ValueError('Expected YYYY-MM-DD')


def parse_time(value):
    if type(value) is time and value.tzinfo is None:
        return value
    if isinstance(value, str) and re.fullmatch(r'\d{2}:\d{2}(:\d{2})?', value):
        return time.fromisoformat(value)
    raise ValueError('Expected local HH:MM or HH:MM:SS')


LocalDate = Annotated[date, BeforeValidator(parse_date)]
LocalTime = Annotated[time, BeforeValidator(parse_time)]
EntityId = Annotated[int, Field(ge=1, le=9223372036854775807)]
Title = Annotated[str, Field(min_length=1, max_length=200)]
Note = Annotated[str, Field(max_length=5000)]
Status = Literal['todo', 'in_progress', 'done']


class PlannerInput(RequestModel):
    model_config = {'extra': 'forbid', 'strict': True, 'str_strip_whitespace': True}


class CourseCreate(PlannerInput):
    name: Title
    semester_name: Title
    starts_on: LocalDate
    ends_on: LocalDate

    @model_validator(mode='after')
    def date_order(self):
        if self.ends_on < self.starts_on:
            raise ValueError('Semester end must not precede start')
        return self


class MeetingCreate(PlannerInput):
    weekday: Annotated[int, Field(ge=1, le=7)]
    starts_at: LocalTime
    ends_at: LocalTime
    location: Annotated[str, Field(max_length=300)] | None = None

    @model_validator(mode='after')
    def time_order(self):
        if self.ends_at <= self.starts_at:
            raise ValueError('Meeting end must follow start')
        return self


class TaskCreate(PlannerInput):
    title: Title
    description: Note | None = None
    planned_on: LocalDate | None = None
    due_on: LocalDate | None = None
    due_time: LocalTime | None = None
    course_id: EntityId | None = None

    @model_validator(mode='after')
    def deadline_date(self):
        if self.due_time is not None and self.due_on is None:
            raise ValueError('Deadline time requires a date')
        return self


class TaskBatch(PlannerInput):
    items: Annotated[list[TaskCreate], Field(min_length=1, max_length=50)]


class PatchInput(PlannerInput):
    nullable: ClassVar[set[str]] = set()

    @model_validator(mode='after')
    def changes(self):
        if not self.model_fields_set:
            raise ValueError('At least one field is required')
        for name in self.model_fields_set - self.nullable:
            if getattr(self, name) is None:
                raise ValueError('Required fields cannot be null')
        return self


class CoursePatch(PatchInput):
    name: Title | None = None
    semester_name: Title | None = None
    starts_on: LocalDate | None = None
    ends_on: LocalDate | None = None


class MeetingPatch(PatchInput):
    nullable = {'location'}
    weekday: Annotated[int, Field(ge=1, le=7)] | None = None
    starts_at: LocalTime | None = None
    ends_at: LocalTime | None = None
    location: Annotated[str, Field(max_length=300)] | None = None


class TaskPatch(PatchInput):
    nullable = {'description', 'planned_on', 'due_on', 'due_time', 'course_id'}
    title: Title | None = None
    description: Note | None = None
    planned_on: LocalDate | None = None
    due_on: LocalDate | None = None
    due_time: LocalTime | None = None
    course_id: EntityId | None = None
    status: Status | None = None
