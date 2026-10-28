"""Read-only briefing contracts, bounded facts and explicit synthetic preview."""
from datetime import date, datetime, timedelta
from typing import Annotated
from zoneinfo import ZoneInfo
from pydantic import Field, model_validator
from backend.schemas import RequestModel


class BriefingRequest(RequestModel):
    date: Annotated[str | None, Field(pattern=r'^\d{4}-\d{2}-\d{2}$')] = None
    location: Annotated[str | None, Field(min_length=1,max_length=200)] = None

    @model_validator(mode='after')
    def actual_date(self):
        if self.date is not None:
            date.fromisoformat(self.date)
        return self


def task_group(row, day, now):
    due, deadline_time = row.get('due_on'), row.get('due_time')
    if due and (due < day or (due == day == now.date() and deadline_time and deadline_time < now.time())):
        return 'overdue'
    return 'today' if row.get('planned_on') == day or due == day else 'remaining'


def briefing_facts(name, result, call_id):
    weather=result.get('weather',result)
    facts={call_id+'.weather':{k:weather.get(k) for k in ('status','location','date','current','daily','fetched_at','errors')}}
    facts[call_id+'.weather']['hourly']=weather.get('hourly',[])[:8]
    if name=='get_daily_briefing':
        facts[call_id+'.briefing']={
            'date':result['date'], 'calendar_status':result.get('calendar_status','ok'),
            'classes':[{k:row.get(k) for k in ('course_name','starts_at','ends_at','location')} for row in result['classes'][:12]],
            'tasks':[{k:row.get(k) for k in ('title','planned_on','due_on','due_time','status','task_group')} for row in result['tasks'][:20]],
            'task_group_counts':{group:sum(row.get('task_group') == group for row in result['tasks']) for group in ('overdue','today','remaining')},
            'class_count':len(result['classes']), 'task_count':len(result['tasks']),
            'counts_are_lower_bounds':bool(result.get('has_more_classes') or result.get('has_more_tasks')),
            'has_more_classes':result.get('has_more_classes',False) or len(result['classes'])>12,
            'has_more_tasks':result.get('has_more_tasks',False) or len(result['tasks'])>20}
    return {'tool':name,'facts':facts}


def preview_briefing():
    today=datetime.now(ZoneInfo('Asia/Seoul')).date().isoformat()
    return {'kind':'briefing','preview':True,'date':today,'calendar_status':'ok',
        'classes':[{'course_name':name,'starts_at':start,'ends_at':end,'location':place} for name,start,end,place in [
            ('인공지능 개론','09:00','10:15','공학관 301'),('뇌과학의 이해','13:00','14:15','자연과학관 202'),('캡스톤디자인','15:00','17:00','프로젝트실')]],
        'tasks':[
            {'title':'뇌 분석 보고서 초안 작성','status':'todo','due_on':(date.fromisoformat(today)-timedelta(days=1)).isoformat(),'due_time':'18:00','task_group':'overdue'},
            {'title':'발표 자료 정리','status':'in_progress','planned_on':today,'due_on':today,'task_group':'today'},
            {'title':'참고 논문 읽기','status':'todo','task_group':'remaining'}],
        'weather':{'status':'ok','location':'춘천','date':today,'preview':True,'source':'더미 날씨',
            'current':{'temperature_c':18,'humidity_pct':60,'precipitation':'없음','observed_at':None},
            'daily':{'low_c':12,'high_c':21},'hourly':[],'cached':False,'fetched_at':None,'errors':[]}}
