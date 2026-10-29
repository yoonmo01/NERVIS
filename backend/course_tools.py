"""Course registration drafts use the existing conversation transaction."""
from copy import deepcopy
from datetime import date, datetime, timedelta
import re
from zoneinfo import ZoneInfo
from typing import Annotated, Literal
from pydantic import Field
from fastapi.encoders import jsonable_encoder
from backend.planner import PlannerError
from backend.planner_schemas import PlannerInput, Title, LocalDate, LocalTime, CourseCreate, MeetingCreate


def semester_defaults(draft, today):
    result=deepcopy(draft)
    name=result.get('semester_name','')
    match=re.fullmatch(r'(?:(\d{4})\s*(?:년\s*|[- ]\s*))?([12])\s*학기',name) or re.fullmatch(r'(\d{4})-([12])',name)
    if match:
        year=int(match[1]) if match[1] else today.year
        if not 1<=year<=9999:raise PlannerError('invalid_semester_year')
        start=date(year,3 if match[2]=='1' else 9,1)
        result['semester_name']=f'{year}년 {match[2]}학기'
        result.setdefault('starts_on',start.isoformat())
        result.setdefault('ends_on',(start+timedelta(days=111)).isoformat())
    return result


class MeetingDraft(PlannerInput):
    weekday: Annotated[int, Field(ge=1,le=7)] | None = None
    starts_at: LocalTime | None = None
    ends_at: LocalTime | None = None
    location: Annotated[str, Field(max_length=300)] | None = None


class CourseDraft(PlannerInput):
    name: Title | None = None
    semester_name: Title | None = None
    starts_on: LocalDate | None = None
    ends_on: LocalDate | None = None
    meetings: Annotated[list[MeetingDraft],Field(max_length=20)] | None = None


class CourseRequest(PlannerInput):
    mode: Literal['apply','answer','cancel']
    courses: Annotated[list[CourseDraft],Field(max_length=10)] = Field(default_factory=list)
    values: CourseDraft = Field(default_factory=CourseDraft)
    confirm: bool = False


def course_preview_requested(command):
    compact = re.sub(r'\s+', '', command)
    return bool(re.search(r'(등록|저장|추가|반영)(?:하기)?전', compact) and
                any(word in compact for word in ('먼저', '설명', '계획', '어떻게', '말해', '알려')))


def course_preview(request):
    lines = ['등록 전에 확인할 계획입니다. 아직 저장하지 않았습니다.']
    drafts = request.courses or [request.values]
    for draft in drafts:
        value = draft.model_dump(mode='json', exclude_none=True)
        lines.append(f"과목명: {value.get('name') or '확인 필요'}.")
        for meeting in value.get('meetings', []):
            weekday = meeting.get('weekday')
            day = '월화수목금토일'[weekday - 1] + '요일' if weekday is not None else '요일 확인 필요'
            lines.append(f"{day} {meeting.get('starts_at') or '시작 시각 확인 필요'}부터 {meeting.get('ends_at') or '종료 시각 확인 필요'}까지, 강의실: {meeting.get('location') or '미지정'}.")
        if not value.get('meetings'):
            lines.append('요일과 수업 시간을 확인해야 합니다.')
    lines.append('학기와 적용 기간, 과목명·강의실 표기를 확인하고 등록을 승인해 주시면 저장합니다.')
    message = ' '.join(lines)
    if len(message) > 1800:
        message = '등록 계획이 길어 화면에서 나누어 확인해야 합니다. 아직 저장하지 않았습니다. 과목을 나누어 알려 주세요.'
    return {'kind': 'course_changes', 'status': 'no_change', 'message': message, 'items': [], 'candidates': []}


class CourseManager:
    def __init__(self,store,conn,state):
        self.store,self.conn,self.state=store,conn,state

    def execute(self,request):
        pending=deepcopy(self.state.get('course_pending'))
        def receipt(status,message,items=None):
            return {'kind':'course_changes','status':status,'message':message,'items':items or [],'candidates':[]}
        def wait(message,index):
            pending['index']=index
            self.state['course_pending']=pending
            return receipt('needs_input',message)
        if request.mode=='cancel':
            self.state['course_pending']=None
            return receipt('cancelled' if pending else 'no_change','확인 중인 수업 등록을 취소했습니다. 저장된 수업은 변경하지 않았습니다.' if pending else '확인 중인 수업 등록이 없습니다.')
        if self.state.get('pending'):raise PlannerError('task_pending_exists',409)
        if request.mode=='apply':
            if pending:return receipt('needs_input','먼저 확인 중인 수업 등록에 답하거나 취소해 주세요.')
            if not request.courses:raise PlannerError('courses_required')
            pending={'courses':[c.model_dump(mode='json',exclude_none=True) for c in request.courses],'index':0,'confirmed':[]}
        else:
            if not pending:return receipt('no_change','확인 중인 수업 등록이 없습니다.')
            changes=request.values.model_dump(mode='json',exclude_none=True)
            pending['courses'][pending['index']].update(changes)
            # Any draft change invalidates prior duplicate confirmation.
            pending['confirmed']=[i for i in pending['confirmed'] if i!=pending['index']]
            if request.confirm and not changes:pending['confirmed'].append(pending['index'])
        labels={'name':'과목명','semester_name':'학기명','starts_on':'학기 시작일','ends_on':'학기 종료일'}
        validated=[]
        names=set()
        for index,original in enumerate(pending['courses']):
            draft=semester_defaults(original,datetime.now(ZoneInfo('Asia/Seoul')).date())
            if 'semester_name' in draft:original['semester_name']=draft['semester_name']
            for field,label in labels.items():
                if not draft.get(field):return wait(f'{index+1}번째 수업의 {label}을 알려주세요.',index)
            if not draft.get('meetings'):return wait(f'“{draft["name"]}”의 요일과 시작·종료 시각을 알려주세요.',index)
            for number,meeting in enumerate(draft['meetings']):
                if any(meeting.get(k) is None for k in ('weekday','starts_at','ends_at')):
                    return wait(f'“{draft["name"]}”의 {number+1}번째 수업 시간에 필요한 요일·시작·종료 시각을 알려주세요.',index)
            course=CourseCreate.model_validate({k:draft[k] for k in labels})
            meetings=[MeetingCreate.model_validate(m) for m in draft['meetings']]
            keys=[(m.weekday,m.starts_at) for m in meetings]
            if len(set(keys))!=len(keys):raise PlannerError('duplicate_course_meetings',409)
            signature=(course.name,course.semester_name,course.starts_on,course.ends_on)
            if signature in names:raise PlannerError('duplicate_courses_in_batch',409)
            names.add(signature)
            duplicate=self.conn.execute('SELECT id FROM courses WHERE name=%s AND semester_name=%s AND starts_on=%s AND ends_on=%s LIMIT 1',signature).fetchone()
            if duplicate and index not in pending['confirmed']:
                return wait(f'“{course.name}”이 같은 학기·기간으로 이미 등록돼 있습니다. 별도 수업으로 하나 더 등록할까요?',index)
            validated.append((course,meetings))
        items=[]
        with self.conn.transaction():
            for course,meetings in validated:
                row=self.store._insert(self.conn,'courses',course.model_dump())
                for meeting in meetings:
                    self.store._insert(self.conn,'class_meetings',{'course_id':row['id'],**meeting.model_dump()})
                items.append({**course.model_dump(),'id':row['id'],'meetings':[{**m.model_dump()} for m in meetings]})
        self.state['course_pending']=None
        days='월화수목금토일'
        lines=[f'“{item["name"]}” · {item["semester_name"]} · {item["starts_on"]}~{item["ends_on"]}\n'+
               '\n'.join(f'{days[m["weekday"]-1]}요일 {m["starts_at"].strftime("%H:%M")}~{m["ends_at"].strftime("%H:%M")}' + (f' · {m["location"]}' if m['location'] else '') for m in item['meetings']) for item in items]
        return receipt('saved','수업을 등록했습니다.\n'+'\n'.join(lines),jsonable_encoder(items))
