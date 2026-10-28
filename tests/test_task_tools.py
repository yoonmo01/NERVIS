"""Mock model and disposable PostgreSQL only; no live API requests."""
import json
import os
import unittest
from dataclasses import replace
from pathlib import Path
from uuid import uuid4
import httpx
from test_analysis import PackageCase
from test_ai import call,response
from backend.ai import AnalysisAI, Gateway, Settings

@unittest.skipUnless(os.environ.get('NERVIS_RUN_DB_TESTS')=='1','isolated DB opt-in')
class TaskToolTests(PackageCase):
    @classmethod
    def setUpClass(cls):
        from backend.planner import DatabaseSettings
        from backend.conversations import ConversationStore
        from psycopg import sql
        cls.settings=DatabaseSettings.load(); cls.database='nervis_task_test_'+uuid4().hex
        with cls.settings.connect(autocommit=True) as conn:
            conn.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(cls.database)))
        cls.store=ConversationStore(replace(cls.settings,dbname=cls.database))
        try:
            with cls.store.settings.connect() as conn:
                for path in sorted(Path('database/migrations').glob('*.sql')):conn.execute(path.read_text(encoding='utf-8-sig'))
        except BaseException:cls.tearDownClass();raise
    @classmethod
    def tearDownClass(cls):
        from psycopg import sql
        assert cls.database.startswith('nervis_task_test_')
        with cls.settings.connect(autocommit=True) as conn:
            conn.execute(sql.SQL('DROP DATABASE {} WITH (FORCE)').format(sql.Identifier(cls.database)))
    def setUp(self):
        super().setUp()
        self.conn=self.enterContext(self.store.settings.connect())
        assert self.database.startswith('nervis_task_test_')
        self.conn.execute('TRUNCATE courses, tasks RESTART IDENTITY CASCADE');self.conn.commit()
        from backend.task_tools import TaskManager,TaskToolRequest
        self.manager=TaskManager(self.store,self.conn,{})
        self.request=TaskToolRequest
    def run_tool(self,**kwargs):return self.manager.execute(self.request.model_validate(kwargs))
    def course_tool(self,**kwargs):
        from backend.course_tools import CourseManager,CourseRequest
        return CourseManager(self.store,self.conn,self.manager.state).execute(CourseRequest.model_validate(kwargs))

    def test_course_draft_missing_followup_cancel_and_multiple_meetings(self):
        result=self.course_tool(mode='apply',courses=[{'name':'합성 과목'}])
        self.assertEqual(result['status'],'needs_input')
        self.assertEqual(self.conn.execute('SELECT count(*) AS n FROM courses').fetchone()['n'],0)
        # Reconstruct from persisted JSON, as a new HTTP turn after browser reload would.
        self.manager.state=json.loads(json.dumps(self.manager.state))
        result=self.course_tool(mode='answer',values={'semester_name':'2026-2','starts_on':'2026-09-01','ends_on':'2026-12-20','meetings':[
            {'weekday':1,'starts_at':'09:00','ends_at':'10:15','location':'301'}, {'weekday':3,'starts_at':'10:00','ends_at':'11:00'}]})
        self.assertEqual(result['status'],'saved')
        self.assertEqual(len(result['items'][0]['meetings']),2)
        self.assertIsNone(result['items'][0]['meetings'][1]['location'])
        self.course_tool(mode='apply',courses=[{'name':'취소할 과목'}])
        self.assertEqual(self.course_tool(mode='cancel')['status'],'cancelled')
        self.assertEqual(self.conn.execute('SELECT count(*) AS n FROM courses').fetchone()['n'],1)

    def test_course_batch_waits_then_duplicate_requires_agreement(self):
        draft={'name':'합성A','semester_name':'2026-2','starts_on':'2026-09-01','ends_on':'2026-12-20','meetings':[{'weekday':1,'starts_at':'09:00','ends_at':'10:00'}]}
        result=self.course_tool(mode='apply',courses=[draft,{'name':'합성B'}])
        self.assertEqual(result['status'],'needs_input')
        self.assertEqual(self.conn.execute('SELECT count(*) AS n FROM courses').fetchone()['n'],0)
        result=self.course_tool(mode='answer',values={**draft,'name':'합성B'})
        self.assertEqual(len(result['items']),2)
        self.assertEqual(self.course_tool(mode='apply',courses=[draft])['status'],'needs_input')
        self.assertEqual(self.course_tool(mode='answer',confirm=True)['status'],'saved')

    def test_course_invalid_times_write_nothing(self):
        from pydantic import ValidationError
        with self.assertRaises(ValidationError):
            self.course_tool(mode='apply',courses=[{'name':'잘못된 시간','semester_name':'2026-2','starts_on':'2026-09-01','ends_on':'2026-12-20','meetings':[{'weekday':1,'starts_at':'12:00','ends_at':'10:00'}]}])
        self.assertEqual(self.conn.execute('SELECT count(*) AS n FROM courses').fetchone()['n'],0)

    def test_course_standard_semester_registers_without_dates(self):
        result=self.course_tool(mode='apply',courses=[{'name':'기본 학기 시험','semester_name':'2027년 2학기',
            'meetings':[{'weekday':1,'starts_at':'09:00','ends_at':'10:00'}]}])
        self.assertEqual(result['status'],'saved')
        self.assertEqual(result['items'][0]['starts_on'],'2027-09-01')
        self.assertEqual(result['items'][0]['ends_on'],'2027-12-21')

    def test_mock_http_course_followup_reloads_and_enters_briefing(self):
        from backend.app import create_app
        from fastapi.testclient import TestClient
        from datetime import date
        packets=[response([call('register_courses',{'mode':'apply','courses':[{'name':'합성 AI 수업'}]})]),
                 response([{'type':'message','content':[{'type':'output_text','text':'수업 시간표 등록'}]}]),
                 response([call('register_courses',{'mode':'answer','values':{'semester_name':'2026-2','starts_on':'2026-09-01','ends_on':'2026-12-20','meetings':[{'weekday':1,'starts_at':'09:00','ends_at':'10:15','location':'301'}]}})])]
        captured=[]
        def handler(request):
            captured.append(json.loads(request.content))
            return httpx.Response(200,json=packets.pop(0))
        with httpx.Client(transport=httpx.MockTransport(handler)) as transport:
            ai=AnalysisAI(Gateway(Settings('fake','synthetic-model',3),client=transport))
            app=create_app(self.package,ai_service=ai,conversation_store=self.store)
            with TestClient(app,base_url='http://127.0.0.1') as client:
                sid=client.post('/api/conversations',json={}).json()['id']
                result=client.post('/api/ai/chat',json={'session_id':sid,'request_id':str(uuid4()),'command':'합성 AI 수업 등록해줘'})
                self.assertEqual(result.status_code,200,result.text)
                self.assertEqual(result.json()['results'][0]['data']['status'],'needs_input')
                self.assertIsNotNone(client.get('/api/conversations/'+sid).json()['state']['planner']['course_pending'])
            with TestClient(app,base_url='http://127.0.0.1') as client:
                body={'session_id':sid,'request_id':str(uuid4()),'command':'2026-2학기, 9월1일부터12월20일, 월요일9시~10시15분, 301'}
                result=client.post('/api/ai/chat',json=body)
                self.assertEqual(result.status_code,200,result.text)
                self.assertEqual(result.json()['results'][0]['data']['status'],'saved')
                self.assertEqual(client.post('/api/ai/chat',json=body).json(),result.json())
                self.assertEqual(len(self.store.list_courses()),1)
                self.assertEqual(len(self.store.daily(date(2026,10,26),'춘천')['classes']),1)
                self.assertNotIn('합성 AI 수업',json.dumps(result.json().get('selection',{})))
        self.assertEqual(len(captured),3)

    def test_task_scenarios_with_persisted_session_and_reload(self):
        from backend.task_tools import TaskManager,TaskToolRequest
        sid=self.store.create()['id']
        def turn(command,**args):
            def run(history,state,conn):
                manager=TaskManager(self.store,conn,state.get('planner'))
                result=manager.execute(TaskToolRequest.model_validate(args))
                return {'model_acknowledgement':result['message'],'results':[], 'planner_state':manager.state}
            self.store.chat(sid,uuid4(),command,{},run)
            return self.store.get(sid)['state']['planner']
        pending=turn('날짜 미정',mode='apply',actions=[{'operation':'create','values':{'title':'새로고침 시험','due_time':'18:00'}}])
        self.assertIsNotNone(pending['pending'])
        self.assertEqual(self.store.list_tasks(),[])
        turn('10월29일',mode='answer',values={'due_on':'2026-10-29'})
        self.assertEqual(str(self.store.list_tasks()[0]['due_on']),'2026-10-29')
        turn('취소할 초안',mode='apply',actions=[{'operation':'create','values':{'title':'취소 시험','due_time':'12:00'}}])
        turn('취소',mode='cancel')
        self.assertEqual(len(self.store.list_tasks()),1)
        turn('두번째 등록',mode='apply',actions=[{'operation':'create','values':{'title':'새로고침 시험B'}}])
        pending=turn('둘 중 완료',mode='apply',actions=[{'operation':'complete','query':'새로고침'}])
        chosen=pending['pending']['actions'][0]['candidates'][1]['id']
        turn('2번',mode='answer',selection=2)
        self.assertEqual(self.conn.execute('SELECT status FROM tasks WHERE id=%s',(chosen,)).fetchone()['status'],'done')
    def create(self,title,**values):
        return self.run_tool(mode='apply',actions=[{'operation':'create','values':{'title':title,**values}}])
    def test_register_modify_complete_and_no_invented_time(self):
        result=self.create('공모전 제출',due_on='2026-10-29')
        self.assertEqual(result['status'],'saved')
        task=result['items'][0]; self.assertIsNone(task['due_time'])
        self.run_tool(mode='apply',actions=[{'operation':'update','values':{'due_time':'18:00'}}])
        result=self.run_tool(mode='apply',actions=[{'operation':'complete'}])
        self.assertEqual(result['items'][0]['status'],'done')
        row=self.conn.execute('SELECT * FROM tasks WHERE id=%s',(task['id'],)).fetchone()
        self.assertEqual(str(row['due_time']),'18:00:00');self.assertIsNotNone(row['completed_at'])
    def test_ambiguity_select_and_cancel(self):
        self.create('보고서 A'); second=self.create('보고서 B')['items'][0]
        result=self.run_tool(mode='apply',actions=[{'operation':'complete','query':'보고서'}])
        self.assertEqual(result['status'],'needs_input');self.assertEqual(len(result['candidates']),2)
        result=self.run_tool(mode='answer',selection=2)
        self.assertEqual(result['items'][0]['id'],second['id'])
        result=self.run_tool(mode='apply',actions=[{'operation':'update','query':'보고서'}])
        self.assertEqual(result['status'],'needs_input')
        self.assertEqual(self.run_tool(mode='cancel')['status'],'cancelled')
        self.assertIsNone(self.manager.state['pending'])
    def test_missing_date_and_atomic_batch(self):
        result=self.run_tool(mode='apply',actions=[{'operation':'create','values':{'title':'첫 작업'}},{'operation':'create','values':{'title':'두 번째','due_time':'18:00'}}])
        self.assertEqual(result['status'],'needs_input')
        self.assertEqual(self.conn.execute('SELECT count(*) AS n FROM tasks').fetchone()['n'],0)
        result=self.run_tool(mode='answer',values={'due_on':'2026-10-29'})
        self.assertEqual(result['status'],'saved');self.assertEqual(len(result['items']),2)
    def test_duplicate_and_stale_selection_need_confirmation(self):
        task=self.create('중복 검사')['items'][0]
        self.assertEqual(self.create('중복 검사')['status'],'needs_input')
        self.assertEqual(self.run_tool(mode='answer',confirm=True)['status'],'saved')
        result=self.run_tool(mode='apply',actions=[{'operation':'complete','query':'중복 검사'}])
        self.conn.execute("UPDATE tasks SET title='수동 변경' WHERE id=%s",(task['id'],))
        result=self.run_tool(mode='answer',selection=1)
        self.assertEqual(result['status'],'needs_input')
        self.assertEqual(self.conn.execute('SELECT status FROM tasks WHERE id=%s',(task['id'],)).fetchone()['status'],'todo')
    def test_mock_http_followup_persists_pending_and_replay_does_not_write_twice(self):
        from backend.app import create_app
        from fastapi.testclient import TestClient
        packets=[response([call('manage_tasks',{'mode':'apply','actions':[{'operation':'create','values':{'title':'검증 제출','due_time':'18:00'}}]})]),response([{'type':'message','content':[{'type':'output_text','text':'제출 일정 등록'}]}]),response([call('manage_tasks',{'mode':'answer','values':{'due_on':'2026-10-29'}})])]
        captured=[]
        def handler(request):captured.append(json.loads(request.content));return httpx.Response(200,json=packets.pop(0))
        with httpx.Client(transport=httpx.MockTransport(handler)) as transport:
            ai=AnalysisAI(Gateway(Settings('fake','synthetic-model',3),client=transport))
            with TestClient(create_app(self.package,ai_service=ai,conversation_store=self.store),base_url='http://127.0.0.1') as client:
                sid=client.post('/api/conversations',json={}).json()['id']
                first=client.post('/api/ai/chat',json={'session_id':sid,'request_id':str(uuid4()),'command':'제출은 오후6시까지 해야 해'})
                self.assertEqual(first.status_code,200,first.text)
                self.assertEqual(first.json()['results'][0]['data']['status'],'needs_input')
                self.assertIsNotNone(client.get('/api/conversations/'+sid).json()['state']['planner']['pending'])
                body={'session_id':sid,'request_id':str(uuid4()),'command':'10월29일까지'}
                second=client.post('/api/ai/chat',json=body)
                self.assertEqual(second.status_code,200,second.text)
                self.assertEqual(second.json()['results'][0]['data']['status'],'saved')
                self.assertEqual(client.post('/api/ai/chat',json=body).json(),second.json())
                self.assertEqual(len(captured),3)
                self.assertEqual(len(self.store.list_tasks()),1)
                packet=json.loads(captured[2]['input'][-1]['content'])
                self.assertIsNotNone(packet['session_state']['planner']['pending'])
                self.assertNotIn('title',packet['session_state'])

    def test_clear_deadline_ignores_implicit_null_and_rejects_duplicate_batch(self):
        from backend.planner import PlannerError
        task=self.create('날짜 정리',due_on='2026-10-29',due_time='18:00')['items'][0]
        result=self.run_tool(mode='apply',actions=[{'operation':'update','values':{'title':'이름 변경','due_on':None}}])
        self.assertEqual(result['items'][0]['due_on'],'2026-10-29')
        result=self.run_tool(mode='apply',actions=[{'operation':'update','clear_fields':['due_on']}])
        self.assertIsNone(result['items'][0]['due_on']);self.assertIsNone(result['items'][0]['due_time'])
        item={'operation':'create','values':{'title':'동일 항목'}}
        with self.assertRaises(PlannerError):self.run_tool(mode='apply',actions=[item,item])
        self.assertEqual(self.conn.execute('SELECT count(*) AS n FROM tasks').fetchone()['n'],1)

    def test_read_only_interjection_preserves_frozen_candidate_choices(self):
        first=self.create('고정 후보 A')['items'][0]; self.create('고정 후보 B')
        self.manager.list_tasks(query='고정 후보')
        self.run_tool(mode='apply',actions=[{'operation':'complete'}])
        self.manager.list_tasks(query='고정 후보 B')
        result=self.run_tool(mode='answer',values={'due_on':'2026-10-29'})
        self.assertEqual(result['status'],'needs_input')
        self.assertEqual(result['candidates'][0]['id'],first['id'])

    def test_failure_after_mutation_rolls_back_before_recording_failed_turn(self):
        from backend.ai import AIError
        sid=self.store.create()['id']
        def fail(history,state,conn):
            from backend.task_tools import TaskManager,TaskToolRequest
            manager=TaskManager(self.store,conn,{})
            manager.execute(TaskToolRequest.model_validate({'mode':'apply','actions':[{'operation':'create','values':{'title':'롤백 검증'}}]}))
            raise AIError('synthetic_failure')
        with self.assertRaises(AIError):self.store.chat(sid,uuid4(),'합성 등록 요청',{},fail)
        self.assertEqual(self.store.list_tasks(),[])
        self.assertEqual(self.store.get(sid)['messages'][0]['status'],'failed')

    def test_stale_target_stays_pending_until_explicit_confirmation(self):
        task=self.create('변경 확인 A')['items'][0];self.create('변경 확인 B')
        self.run_tool(mode='apply',actions=[{'operation':'complete','query':'변경 확인'}])
        self.conn.execute("UPDATE tasks SET title='외부에서 바뀐 이름' WHERE id=%s",(task['id'],))
        self.assertEqual(self.run_tool(mode='answer',selection=1)['status'],'needs_input')
        self.assertEqual(self.run_tool(mode='answer',values={'due_on':'2026-10-29'})['status'],'needs_input')
        self.assertEqual(self.run_tool(mode='answer',confirm=True)['status'],'saved')

    def test_missing_complete_target_can_be_corrected_to_existing_task(self):
        task=self.create('정확한 제출')['items'][0]
        self.assertEqual(self.run_tool(mode='apply',actions=[{'operation':'complete','query':'틀린 제목'}])['status'],'needs_input')
        result=self.run_tool(mode='answer',query='정확한 제출')
        self.assertEqual(result['status'],'saved');self.assertEqual(result['items'][0]['id'],task['id'])
        self.assertEqual(self.conn.execute('SELECT count(*) AS n FROM tasks').fetchone()['n'],1)

    def test_clear_missing_time_allows_registration_without_deadline(self):
        self.assertEqual(self.create('시간 없는 등록',due_time='18:00')['status'],'needs_input')
        result=self.run_tool(mode='answer',clear_fields=['due_time'])
        self.assertEqual(result['status'],'saved');self.assertIsNone(result['items'][0]['due_time'])
