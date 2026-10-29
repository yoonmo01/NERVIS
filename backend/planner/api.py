"""Local-only calendar/task routes; no external model requests."""
from datetime import datetime
from threading import Lock
from typing import Annotated
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Header, HTTPException, Path, Query, Request, Response

from backend.planner.store import DatabaseSettings, PlannerStore
from backend.planner.store import PlannerError
from backend.planner.briefing import preview_briefing
from backend.weather.service import WeatherService
from backend.planner.schemas import (CourseCreate, CoursePatch, MeetingCreate, MeetingPatch,
                                     TaskCreate, TaskPatch, TaskBatch, LocalDate, Status)

LOCAL_ORIGINS = {'http://localhost:5173', 'http://127.0.0.1:5173',
                 'http://localhost:8000', 'http://127.0.0.1:8000'}
store_lock = Lock()


def check_origin(request: Request):
    if request.method not in ('GET', 'HEAD') and request.headers.get('origin') not in (None, *LOCAL_ORIGINS):
        raise HTTPException(403, 'Planner origin is not allowed')


def get_store(request: Request):
    with store_lock:
        if request.app.state.planner_store is None:
            request.app.state.planner_store = PlannerStore(DatabaseSettings.load())
        return request.app.state.planner_store


Store = Annotated[PlannerStore, Depends(get_store)]


def get_weather(request: Request):
    with store_lock:
        if request.app.state.weather_service is None:
            request.app.state.weather_service = WeatherService.load()
        return request.app.state.weather_service


Weather = Annotated[WeatherService, Depends(get_weather)]
Id = Annotated[int, Path(ge=1, le=9223372036854775807)]
Key = Annotated[UUID, Header(alias='Idempotency-Key')]
Limit = Annotated[int, Query(ge=1, le=200)]
Offset = Annotated[int, Query(ge=0, le=1000000)]
router = APIRouter(prefix='/api', tags=['planner (local)'], dependencies=[Depends(check_origin)])


@router.get('/db/status')
def db_status(store: Store):
    return store.status()


@router.get('/courses')
def courses(store: Store, semester: Annotated[str | None, Query(max_length=200)] = None,
            limit: Limit = 100, offset: Offset = 0):
    return store.list_courses(semester, limit, offset)


@router.get('/courses/{course_id}')
def course(course_id: Id, store: Store):
    return store.get('courses', course_id)


@router.post('/courses', status_code=201)
def add_course(body: CourseCreate, store: Store, key: Key):
    return store.create_course(body, key)


@router.patch('/courses/{course_id}')
def change_course(course_id: Id, body: CoursePatch, store: Store):
    return store.update('courses', course_id, body)


@router.delete('/courses/{course_id}', status_code=204)
def remove_course(course_id: Id, store: Store):
    store.delete('courses', course_id)
    return Response(status_code=204)


@router.get('/courses/{course_id}/meetings')
def meetings(course_id: Id, store: Store, limit: Limit = 100, offset: Offset = 0):
    return store.list_meetings(course_id, limit, offset)


@router.get('/class-meetings/{meeting_id}')
def meeting(meeting_id: Id, store: Store):
    return store.get('class_meetings', meeting_id)


@router.post('/courses/{course_id}/meetings', status_code=201)
def add_meeting(course_id: Id, body: MeetingCreate, store: Store, key: Key):
    return store.create_meeting(course_id, body, key)


@router.patch('/class-meetings/{meeting_id}')
def change_meeting(meeting_id: Id, body: MeetingPatch, store: Store):
    return store.update('class_meetings', meeting_id, body)


@router.delete('/class-meetings/{meeting_id}', status_code=204)
def remove_meeting(meeting_id: Id, store: Store):
    store.delete('class_meetings', meeting_id)
    return Response(status_code=204)


@router.get('/tasks')
def tasks(store: Store, status: Status | None = None, planned_on: LocalDate | None = None,
          due_before: LocalDate | None = None, course_id: Annotated[int | None, Query(ge=1, le=9223372036854775807)] = None,
          limit: Limit = 100, offset: Offset = 0):
    return store.list_tasks(status=status, planned_on=planned_on, due_before=due_before,
                            course_id=course_id, limit=limit, offset=offset)


@router.post('/tasks', status_code=201)
def add_task(body: TaskCreate, store: Store, key: Key):
    return store.create_task(body, key)


@router.post('/tasks/batch', status_code=201)
def add_tasks(body: TaskBatch, store: Store, key: Key):
    return store.create_tasks(body, key)


@router.get('/tasks/{task_id}')
def task(task_id: Id, store: Store):
    return store.get('tasks', task_id)


@router.patch('/tasks/{task_id}')
def change_task(task_id: Id, body: TaskPatch, store: Store):
    return store.update('tasks', task_id, body)


@router.delete('/tasks/{task_id}', status_code=204)
def remove_task(task_id: Id, store: Store):
    store.delete('tasks', task_id)
    return Response(status_code=204)


@router.get('/briefing')
def briefing(request: Request, day: Annotated[LocalDate | None, Query(alias='date')] = None,
             location: Annotated[str | None, Query(min_length=1, max_length=200)] = None):
    return briefing_result(request, date=day.isoformat() if day else None,location=location)


def briefing_result(request, date=None, location=None):
    from datetime import date as Date
    weather=get_weather(request)
    day=Date.fromisoformat(date) if date else None
    selected_day = day or datetime.now(ZoneInfo('Asia/Seoul')).date()
    try:
        result=get_store(request).daily(selected_day,location or weather.default_location)
        result['calendar_status']='ok'
    except PlannerError:
        result={'date':selected_day,'classes':[],'tasks':[],'calendar_status':'unavailable'}
    result['kind']='briefing'
    result['preview']=False
    result['weather'] = weather.get(location, selected_day)
    return result


@router.get('/briefing/preview')
def briefing_preview():
    return preview_briefing()


@router.get('/weather')
def weather_lookup(weather: Weather, day: Annotated[LocalDate | None, Query(alias='date')] = None,
                   location: Annotated[str | None, Query(min_length=1, max_length=200)] = None):
    return weather.get(location, day)
