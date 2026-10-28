"""Typed task intents, persisted clarification and transactional local receipts."""
from copy import deepcopy
import json
from typing import Annotated, Literal
from pydantic import Field
from fastapi.encoders import jsonable_encoder
from backend.planner import PlannerError
from backend.planner_schemas import PlannerInput, Title, LocalDate, LocalTime, Status, TaskCreate, TaskPatch

class TaskValues(PlannerInput):
    title: Title | None = None
    planned_on: LocalDate | None = None
    due_on: LocalDate | None = None
    due_time: LocalTime | None = None
    status: Status | None = None

ClearField = Literal['planned_on','due_on','due_time']
class TaskAction(PlannerInput):
    operation: Literal['create','update','complete']
    query: Title | None = None
    values: TaskValues = Field(default_factory=TaskValues)
    clear_fields: Annotated[list[ClearField],Field(max_length=3)] = Field(default_factory=list)
    required: Annotated[list[Literal['title','planned_on','due_on','due_time']],Field(max_length=4)] = Field(default_factory=list)

class TaskToolRequest(PlannerInput):
    mode: Literal['apply','answer','cancel']
    actions: Annotated[list[TaskAction],Field(max_length=10)] = Field(default_factory=list)
    query: Title | None = None
    selection: Annotated[int,Field(ge=1,le=10)] | None = None
    values: TaskValues = Field(default_factory=TaskValues)
    clear_fields: Annotated[list[ClearField],Field(max_length=3)] = Field(default_factory=list)
    confirm: bool = False

class TaskListRequest(PlannerInput):
    query: Title | None = None
    status: Status | None = None

FIELDS=('id','title','status','planned_on','due_on','due_time')
def task_summary(row):
    return jsonable_encoder({k:row[k] for k in FIELDS})

def task_facts(tool,result,call_id):
    return {'tool':tool,'facts':{call_id+('.courses' if tool=='register_courses' else '.tasks'):result}}

def task_changes(item):
    changes=item['values'].copy()
    for name in item['clear_fields']:changes[name]=None
    if 'due_on' in item['clear_fields']:changes['due_time']=None
    return changes

class TaskManager:
    def __init__(self,store,conn,state):
        self.store,self.conn=store,conn
        self.state=deepcopy(state) if state else {'pending':None,'last_tasks':[]}
        self.state.setdefault('pending',None);self.state.setdefault('last_tasks',[])

    def public_state(self):
        result=deepcopy(self.state)
        pending=result.get('pending')
        if pending:
            for item in pending['actions']:
                for row in [item.get('target'),*item.get('candidates',[])]:
                    if row:row.pop('updated_at',None)
        return result

    def _search(self,query,status=None,limit=11):
        pattern='%'+query.replace('\\','\\\\').replace('%','\\%').replace('_','\\_')+'%' if query else '%'
        return self.conn.execute('SELECT * FROM tasks WHERE title ILIKE %s AND (%s::text IS NULL OR status=%s) ORDER BY id LIMIT %s',(pattern,status,status,limit)).fetchall()

    def list_tasks(self,query=None,status=None):
        rows=self._search(query,status,21)
        items=[task_summary(r) for r in rows[:20]]
        self.state['last_tasks']=items
        return {'kind':'tasks','status':'listed','items':items,'candidates':[],'has_more':len(rows)>20,
                'message':f'할 일 {len(items)}개를 조회했습니다.' if items else '조건에 맞는 할 일이 없습니다.'}

    def _snapshot(self,row):
        return {**task_summary(row),'updated_at':row['updated_at'].isoformat()}

    def _current(self,task_id):
        row=self.conn.execute('SELECT * FROM tasks WHERE id=%s FOR UPDATE',(task_id,)).fetchone()
        if row is None:raise PlannerError('task_target_no_longer_exists',409)
        return row

    def _wait(self,pending,index,missing,message,candidates=None):
        if candidates and '\n1.' not in message:
            message+='\n'+'\n'.join(f'{i+1}. {r["title"]} · {r["due_on"] or "마감 미지정"}' for i,r in enumerate(candidates))
        pending.update(index=index,missing=missing,message=message)
        self.state['pending']=pending
        return {'kind':'task_changes','status':'needs_input','message':message,'missing_fields':[missing],
                'items':[],'candidates':[task_summary(r) for r in candidates or []]}

    def execute(self,request):
        pending=self.state['pending']
        if self.state.get('course_pending'):raise PlannerError('course_pending_exists',409)
        if request.mode=='cancel':
            if not pending:return {'kind':'task_changes','status':'no_change','message':'확인 중인 요청이 없습니다. 이미 저장한 할 일은 변경하지 않았습니다.','items':[],'candidates':[]}
            self.state['pending']=None
            return {'kind':'task_changes','status':'cancelled','message':'확인 중인 할 일 요청을 취소했습니다. 저장된 할 일은 변경하지 않았습니다.','items':[],'candidates':[]}
        if request.mode=='apply':
            if pending:return self._wait(pending,pending['index'],pending['missing'],'먼저 확인 중인 요청에 답하거나 “취소해”라고 말씀해 주세요.',pending['actions'][pending['index']].get('candidates'))
            if not request.actions:raise PlannerError('task_actions_required')
            pending={'actions':[a.model_dump(mode='json',exclude_none=True) for a in request.actions]}
            for action in pending['actions']:
                action['values']={k:v for k,v in action['values'].items() if v is not None}
            signatures=[json.dumps(a,sort_keys=True,ensure_ascii=False) for a in pending['actions']]
            if len(set(signatures))!=len(signatures):raise PlannerError('duplicate_actions_in_task_batch',409)
        else:
            if not pending:
                return {'kind':'task_changes','status':'no_change','message':'확인 중인 요청이 없습니다. 등록하거나 바꿀 할 일을 말씀해 주세요.','items':[],'candidates':[]}
            item=pending['actions'][pending['index']]
            updates=request.values.model_dump(mode='json',exclude_none=True)
            item['values'].update(updates)
            item['clear_fields']=list(set(item['clear_fields']+request.clear_fields)-set(updates))
            item['required']=[name for name in item['required'] if name not in item['clear_fields']]
            if request.query:
                if item.pop('create_completed',False) and item['values'].get('title')==item.get('query') and 'title' not in updates:
                    item['values'].pop('title',None)
                item['query']=request.query;item.pop('target',None);item.pop('candidates',None)
                item.pop('stale_confirmation',None);item['confirmed']=False
            if request.selection is not None:
                candidates=item.get('candidates',[])
                if request.selection>len(candidates):
                    return self._wait(pending,pending['index'],'selection','목록에 있는 번호를 선택해 주세요.',candidates)
                item['target']=candidates[request.selection-1]
                item.pop('candidates',None)
            if request.confirm and pending['missing']=='confirmation':item['confirmed']=True

        for index,item in enumerate(pending['actions']):
            values=item['values']; operation=item['operation']
            if operation!='create' and not item.get('create_completed'):
                if not item.get('target'):
                    if item.get('candidates'):
                        return self._wait(pending,index,'selection','수정할 할 일의 번호를 선택해 주세요.',item['candidates'])
                    query=item.get('query')
                    if query:
                        rows=self._search(query)
                        exact=[r for r in rows if r['title'].casefold()==query.casefold()]
                        if len(exact)==1:rows=exact
                    else:
                        if len(self.state['last_tasks'])>10:return self._wait(pending,index,'query','어떤 할 일인지 이름을 알려 주세요.')
                        rows=[self._current(r['id']) for r in self.state['last_tasks'][:10]]
                    if not rows:
                        if operation=='complete' and query:
                            item['create_completed']=True
                            values.setdefault('title',query);values['status']='done'
                            return self._wait(pending,index,'confirmation',f'“{values["title"]}”라는 기존 할 일을 찾지 못했습니다. 새 완료 기록으로 추가할까요?')
                        return self._wait(pending,index,'query','어떤 할 일을 바꿀까요? 할 일 이름을 알려 주세요.')
                    if len(rows)>10:return self._wait(pending,index,'query','일치하는 할 일이 많습니다. 이름을 더 구체적으로 알려 주세요.')
                    if len(rows)>1:
                        item['candidates']=[self._snapshot(r) for r in rows]
                        text='같은 이름으로 찾은 할 일이 여러 개입니다. 번호를 선택해 주세요.\n'+'\n'.join(f'{i+1}. {r["title"]} · {r["due_on"] or "마감 미지정"}' for i,r in enumerate(rows))
                        return self._wait(pending,index,'selection',text,rows)
                    item['target']=self._snapshot(rows[0])
                current=self._current(item['target']['id'])
                if current['updated_at'].isoformat()!=item['target']['updated_at']:
                    item['target']=self._snapshot(current);item['confirmed']=False;item['stale_confirmation']=True
                    return self._wait(pending,index,'confirmation',f'대상 할 일이 다른 곳에서 변경됐습니다. 현재 “{current["title"]}”에 변경을 적용할까요?')
                if item.get('stale_confirmation') and not item.get('confirmed'):
                    return self._wait(pending,index,'confirmation',f'현재 “{current["title"]}”에 적용할지 확인해 주세요. 적용하려면 “네”라고 말씀해 주세요.')
                merged={**task_summary(current),**task_changes(item)}
            else:merged=task_changes(item)
            if item.get('create_completed') and not item.get('confirmed'):
                return self._wait(pending,index,'confirmation',f'“{values["title"]}”를 새 완료 기록으로 추가할까요?')
            missing=next((name for name in item.get('required',[]) if not merged.get(name)),None)
            if not merged.get('title'):missing='title'
            if merged.get('due_time') and not merged.get('due_on'):missing='due_on'
            if operation=='update' and not values and not item.get('clear_fields'):missing='changes'
            if missing:
                labels={'title':'할 일 이름','due_on':'마감 날짜','due_time':'마감 시간','planned_on':'진행할 날짜','changes':'바꿀 내용'}
                return self._wait(pending,index,missing,f'{labels[missing]}을 알려 주세요.')
            if operation=='create' and not item.get('confirmed'):
                duplicates=[r for r in self._search(values['title']) if r['title'].casefold()==values['title'].casefold() and task_summary(r)['planned_on']==merged.get('planned_on') and task_summary(r)['due_on']==merged.get('due_on')]
                if duplicates:return self._wait(pending,index,'confirmation',f'같은 이름과 날짜의 “{values["title"]}”가 이미 있습니다. 별도 할 일로 하나 더 추가할까요?')
            # Validate every merged item before the first mutation.
            TaskCreate.model_validate({k:merged[k] for k in ('title','planned_on','due_on','due_time') if k in merged})

        receipts=[]
        with self.conn.transaction():
            for item in pending['actions']:
                values=item['values'];operation=item['operation']
                if operation=='create' or item.get('create_completed'):
                    body=TaskCreate.model_validate({k:v for k,v in task_changes(item).items() if k!='status'})
                    row=self.store._insert(self.conn,'tasks',body.model_dump())
                    if values.get('status') and values['status']!='todo':row=self.store._update(self.conn,'tasks',row['id'],TaskPatch(status=values['status']))
                    label='완료 기록 추가' if item.get('create_completed') or values.get('status')=='done' else '등록'
                else:
                    changes=task_changes(item)
                    if operation=='complete':changes['status']='done'
                    row=self.store._update(self.conn,'tasks',item['target']['id'],TaskPatch.model_validate(changes))
                    label='완료 처리' if operation=='complete' else '수정'
                receipts.append({**task_summary(row),'operation':label})
        self.state['pending']=None;self.state['last_tasks']=list({r['id']:{k:r[k] for k in FIELDS} for r in receipts}.values())
        text='\n'.join(f'“{r["title"]}” {r["operation"]}했습니다.'+(f' 예정일은 {r["planned_on"]}입니다.' if r['planned_on'] else '')+(f' 마감은 {r["due_on"]}'+(f' {r["due_time"][:5]}' if r['due_time'] else '')+'입니다.' if r['due_on'] else '') for r in receipts)
        return {'kind':'task_changes','status':'saved','message':text,'items':receipts,'candidates':[]}
