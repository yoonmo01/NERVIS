"""Synthetic messages and mock gateway; DB tests require isolated-db opt-in."""
import json
import os
import unittest
from dataclasses import replace
from pathlib import Path
from uuid import uuid4
import httpx
from test_analysis import PackageCase
from test_ai import response, call
from backend.ai import AnalysisAI, Gateway, Settings, AIError

class HistoryTests(PackageCase):
    def test_followup_includes_original_roles_dates_and_approved_facts_only(self):
        captured=[]
        def handler(request):
            captured.append(json.loads(request.content))
            return httpx.Response(200,json=response([{'type':'message','content':[{'type':'output_text','text':'오후 6시로 이해했습니다. 아직 저장하지 않았습니다.'}]}]))
        with httpx.Client(transport=httpx.MockTransport(handler)) as client:
            ai=AnalysisAI(Gateway(Settings('fake','synthetic-model',1),client=client))
            history=[{'role':'user','content':'내일 보고서 해야 해.'},
                     {'role':'assistant','content':'마감 시간은 언제인가요?'}]
            answer=ai.run(self.load(),'오후 6시',{},history=history,session_state={'last_result_refs':[]})
        self.assertEqual(captured[0]['input'][:2],history)
        self.assertEqual(json.loads(captured[0]['input'][-1]['content'])['command'],'오후 6시')
        self.assertEqual(answer['memory_facts'],[])
        self.assertIn('elapsed_seconds',answer)

    def test_tool_memory_contains_summary_not_raw_signals(self):
        packets=[response([call()]),response([{'type':'message','content':[{'type':'output_text','text':json.dumps({'answer':'두 영역을 비교했습니다.','used_fact_ids':['call_1.comparison']})}]}])]
        with httpx.Client(transport=httpx.MockTransport(lambda r:httpx.Response(200,json=packets.pop(0)))) as client:
            result=AnalysisAI(Gateway(Settings('fake','synthetic-model',2),client=client)).run(self.load(),'비교해줘',{})
        encoded=json.dumps(result['memory_facts'],ensure_ascii=False)
        self.assertIn('call_1.comparison',encoded)
        for text in ('"bold": [','"zscore": [','"samples": [','file_path'):
            self.assertNotIn(text,encoded)

    def test_partial_explanation_keeps_usage_for_both_calls(self):
        packets=[response([call()]),response([{'type':'message','content':[{'type':'output_text','text':'invalid structured answer'}]}])]
        with httpx.Client(transport=httpx.MockTransport(lambda r:httpx.Response(200,json=packets.pop(0)))) as client:
            result=AnalysisAI(Gateway(Settings('fake','synthetic-model',2),client=client)).run(self.load(),'비교해줘',{})
        self.assertEqual(result['status'],'partial')
        self.assertEqual(len(result['usage']),2)
        self.assertEqual(sum(x['input_tokens'] for x in result['usage']),20)

class ConversationTitleTests(unittest.TestCase):
    def test_title_generation_is_separate_short_and_tool_free(self):
        captured=[]
        def handler(request):
            captured.append(json.loads(request.content))
            return httpx.Response(200,json=response([{'type':'message','content':[{'type':'output_text','text':'공모전 제출 일정'}]}]))
        with httpx.Client(transport=httpx.MockTransport(handler)) as client:
            ai=AnalysisAI(Gateway(Settings('fake','synthetic-model',1),client=client))
            result=ai.generate_title('공모전을 10월29일까지 제출해야 돼','등록했습니다.')
        self.assertEqual(result['title'],'공모전 제출 일정')
        self.assertEqual(len(captured),1)
        self.assertNotIn('tools',captured[0])
        self.assertLessEqual(captured[0]['max_output_tokens'],100)
        self.assertEqual(len(captured[0]['input']),1)

    def test_title_is_short_first_sentence_and_empty_fallback(self):
        from backend.conversations import conversation_title
        self.assertEqual(conversation_title(None),'새 대화')
        self.assertEqual(conversation_title('내 프로젝트 별칭은 푸른궤도야. 일정에는 등록하지 마'),'내 프로젝트 별칭은 푸른궤도야')
        self.assertEqual(conversation_title('  전전두피질   좌우 비교해줘\n그리고 설명해줘'),'전전두피질 좌우 비교해줘')
        self.assertLessEqual(len(conversation_title('긴 제목 '*50)),37)

@unittest.skipUnless(os.environ.get('NERVIS_RUN_DB_TESTS')=='1','explicit isolated PostgreSQL integration opt-in')
class ConversationStoreTests(PackageCase):
    def test_title_once_only_preserved_and_not_in_history(self):
        sid=self.store.create()['id']
        self.store.chat(sid,uuid4(),'합성 일정 등록',{},lambda h,s,c:self.result('등록했습니다.'))
        seen=[]
        def generate(command,answer):
            seen.append((command,answer))
            return {'title':'합성 일정 관리','usage':{'input_tokens':12}}
        self.store.generate_title(sid,generate)
        self.store.generate_title(sid,generate)
        self.assertEqual(len(seen),1)
        self.store.chat(sid,uuid4(),'이어가기',{},lambda h,s,c:self.result())
        self.assertEqual(self.store.get(sid)['title'],'합성 일정 관리')
        self.assertEqual(next(s for s in self.store.list()['sessions'] if s['id']==sid)['title'],'합성 일정 관리')
        self.assertNotIn('합성 일정 관리',json.dumps(self.store.get(sid)['messages'],ensure_ascii=False))

    def test_title_failure_keeps_chat_and_never_retries(self):
        sid=self.store.create()['id']
        self.store.chat(sid,uuid4(),'원래 제목',{},lambda h,s,c:self.result())
        calls=[]
        def fail(*args):
            calls.append(1)
            raise AIError('gateway_http_500')
        self.store.generate_title(sid,fail)
        self.store.generate_title(sid,fail)
        self.assertEqual(len(calls),1)
        self.assertEqual(self.store.get(sid)['title'],'원래 제목')
        self.assertEqual(len(self.store.get(sid)['messages']),2)

    @classmethod
    def setUpClass(cls):
        from backend.planner import DatabaseSettings
        from backend.conversations import ConversationStore
        from psycopg import sql
        cls.settings=DatabaseSettings.load()
        cls.database='nervis_session_test_'+uuid4().hex
        with cls.settings.connect(autocommit=True) as conn:
            conn.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(cls.database)))
        cls.store=ConversationStore(replace(cls.settings,dbname=cls.database))
        try:
            with cls.store.settings.connect() as conn:
                for path in sorted(Path('database/migrations').glob('*.sql')):
                    conn.execute(path.read_text(encoding='utf-8'))
        except BaseException:
            cls.tearDownClass()
            raise

    @classmethod
    def tearDownClass(cls):
        from psycopg import sql
        with cls.settings.connect(autocommit=True) as conn:
            conn.execute(sql.SQL('DROP DATABASE {} WITH (FORCE)').format(sql.Identifier(cls.database)))

    def result(self,text='언제까지인가요?'):
        return {'status':'ok','model_acknowledgement':text,'results':[],'warning':None,'usage':[{'input_tokens':12,'output_tokens':5}], 'elapsed_seconds':.1,'memory_facts':[]}

    def test_restore_followup_isolation_and_usage(self):
        sid=self.store.create()['id']; other=self.store.create()['id']
        self.store.chat(sid,uuid4(),'보고서 해야 해',{},lambda h,s,c:self.result())
        seen=[]
        self.store.chat(sid,uuid4(),'내일 6시',{},lambda h,s,c:(seen.extend(h),self.result('이해했습니다.'))[1])
        restored=self.store.get(sid)
        self.assertEqual([m['role'] for m in restored['messages']],['user','assistant','user','assistant'])
        self.assertIn('보고서 해야 해',seen[0]['content'])
        self.assertEqual(restored['messages'][1]['usage'][0]['input_tokens'],12)
        self.assertEqual(self.store.get(other)['messages'],[])

    def test_repeated_request_cached_and_changed_body_rejected(self):
        from backend.planner import PlannerError
        sid=self.store.create()['id']; rid=uuid4(); calls=[]
        run=lambda h,s,c:(calls.append(1),self.result())[1]
        first=self.store.chat(sid,rid,'질문',{},run)
        self.assertEqual(self.store.chat(sid,rid,'질문',{},run),first)
        with self.assertRaises(PlannerError) as error:self.store.chat(sid,rid,'다른 질문',{},run)
        self.assertEqual(error.exception.status,409)
        self.assertEqual(len(calls),1)

    def test_failed_request_not_replayed_and_new_turn_can_continue(self):
        from backend.planner import PlannerError
        sid=self.store.create()['id']; rid=uuid4()
        def fail(h,s,c):raise AIError('gateway_http_503')
        with self.assertRaises(AIError):self.store.chat(sid,rid,'질문',{},fail)
        with self.assertRaises(PlannerError):self.store.chat(sid,rid,'질문',{},lambda h,s,c:self.fail('must not call'))
        seen=[]
        self.store.chat(sid,uuid4(),'다른 질문',{},lambda h,s,c:(seen.extend(h),self.result())[1])
        self.assertEqual(seen,[])
        self.assertEqual(self.store.get(sid)['messages'][0]['status'],'failed')

    def test_same_session_lock_blocks_before_model(self):
        from backend.conversations import session_lock_key
        from backend.planner import PlannerError
        sid=self.store.create()['id']
        with self.store.settings.connect() as conn:
            conn.execute('SELECT pg_advisory_lock(%s)',(session_lock_key(sid),))
            with self.assertRaises(PlannerError) as error:self.store.chat(sid,uuid4(),'질문',{},lambda h,s,c:self.fail('must not call'))
            self.assertEqual(error.exception.status,409)

    def test_http_session_restore_followup_and_invalid_ids(self):
        from fastapi.testclient import TestClient
        from backend.app import create_app
        captured=[]
        def handler(request):
            captured.append(json.loads(request.content))
            return httpx.Response(200,json=response([{'type':'message','content':[{'type':'output_text','text':'마감 시간은 언제인가요?' if len(captured)==1 else '보고서 일정' if len(captured)==2 else '내일 오후 6시로 이해했습니다. 아직 DB에 등록하지 않았습니다.'}]}]))
        with httpx.Client(transport=httpx.MockTransport(handler)) as transport:
            ai=AnalysisAI(Gateway(Settings('fake','synthetic-model',3),client=transport))
            with TestClient(create_app(self.package,ai_service=ai,conversation_store=self.store),base_url='http://127.0.0.1') as client:
                self.assertEqual(client.post('/api/conversations',json={},headers={'origin':'https://other.invalid'}).status_code,403)
                session=client.post('/api/conversations',json={}).json()
                sid=session['id']
                first={'session_id':sid,'request_id':str(uuid4()),'command':'내일 보고서 해야 해'}
                self.assertEqual(client.post('/api/ai/chat',json=first).status_code,200)
                second={'session_id':sid,'request_id':str(uuid4()),'command':'오후 6시까지'}
                answer=client.post('/api/ai/chat',json=second)
                self.assertEqual(answer.status_code,200,answer.text)
                self.assertEqual(len(client.get('/api/conversations/'+sid).json()['messages']),4)
                self.assertIn('내일 보고서',captured[2]['input'][0]['content'])
                self.assertEqual(client.post('/api/ai/chat',json=second).status_code,200)
                self.assertEqual(len(captured),3)
                self.assertEqual(client.post('/api/ai/chat',json={'command':'test','session_id':sid}).status_code,422)
                self.assertEqual(client.get('/api/conversations/not-a-uuid').status_code,422)
                self.assertEqual(client.get('/api/conversations/'+str(uuid4())).status_code,404)

    def test_interrupted_turn_is_not_replayed_and_size_limit_is_explicit(self):
        from backend.planner import PlannerError
        from psycopg.types.json import Jsonb
        sid=self.store.create()['id']; old=uuid4()
        with self.store.settings.connect() as conn:
            conn.execute("INSERT INTO conversation_messages(session_id,request_id,role,content,status) VALUES (%s,%s,'user','interrupted','running')",(sid,old))
        self.store.chat(sid,uuid4(),'계속',{},lambda h,s,c:self.result())
        self.assertEqual(self.store.get(sid)['messages'][0]['status'],'failed')
        with self.store.settings.connect() as conn:
            conn.execute("UPDATE conversation_messages SET metadata=metadata || %s WHERE session_id=%s AND role='assistant'",(Jsonb({'facts':[{'large':'x'*240001}]}),sid))
        with self.assertRaises(PlannerError) as error:
            self.store.chat(sid,uuid4(),'크기 검사',{},lambda h,s,c:self.fail('must not call'))
        self.assertEqual(error.exception.code,'conversation_history_too_large_start_new')

    def test_session_list_titles_stay_stable_and_paginate(self):
        from fastapi.testclient import TestClient
        from backend.app import create_app
        sid=self.store.create()['id']
        self.store.chat(sid,uuid4(),'푸른궤도 발표 준비. 일정에 넣지는 마',{},lambda h,s,c:self.result())
        self.store.chat(sid,uuid4(),'이제 다른 얘기야',{},lambda h,s,c:self.result())
        with TestClient(create_app(self.package,conversation_store=self.store),base_url='http://127.0.0.1') as client:
            page=client.get('/api/conversations?limit=1').json()
            self.assertEqual(len(page['sessions']),1)
            self.assertTrue(page['has_more'])
            item=page['sessions'][0]
            self.assertEqual(item['id'],sid)
            self.assertEqual(item['title'],'푸른궤도 발표 준비')
            self.assertEqual(item['message_count'],4)
            restored=client.get('/api/conversations/'+sid).json()
            self.assertEqual(restored['title'],item['title'])
            self.assertEqual(client.get('/api/conversations?limit=0').status_code,422)
            nextpage=client.get('/api/conversations?limit=1&offset=1').json()
            self.assertNotEqual(nextpage['sessions'][0]['id'],sid)
            for hidden in ('metadata','reply','facts','state'):
                self.assertNotIn(hidden,item)

    def test_empty_sessions_are_filtered_before_pagination(self):
        sid=self.store.create()['id']
        self.store.chat(sid,uuid4(),'목록에 남을 실제 첫 메시지',{},lambda h,s,c:self.result())
        empty_ids=[self.store.create()['id'] for _ in range(3)]
        page=self.store.list(limit=1)
        self.assertEqual(page['sessions'][0]['id'],sid)
        self.assertEqual(page['sessions'][0]['title'],'목록에 남을 실제 첫 메시지')
        listed={row['id'] for row in self.store.list(limit=100)['sessions']}
        self.assertTrue(listed.isdisjoint(empty_ids))
        for empty_id in empty_ids:
            self.assertEqual(self.store.get(empty_id)['messages'],[])
