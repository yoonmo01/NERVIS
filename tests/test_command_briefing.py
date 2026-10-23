import json
from unittest.mock import patch
from fastapi.testclient import TestClient
from test_analysis import PackageCase
from test_ai import response, call
import httpx


class CommandBriefingTests(PackageCase):
    def test_summary_marks_its_own_truncation(self):
        from backend.briefing import briefing_facts
        facts=briefing_facts('get_daily_briefing',{'date':'2026-10-23','classes':[{}]*13,
            'tasks':[{}]*21,'weather':{}},'c')['facts']['c.briefing']
        self.assertTrue(facts['has_more_classes'])
        self.assertTrue(facts['has_more_tasks'])
    def test_daily_tool_uses_service_and_sends_only_bounded_summary(self):
        from backend.ai import AnalysisAI, Gateway, Settings
        packets=[response([call('get_daily_briefing',{'location':None})]),response([{'type':'message','content':[
            {'type':'output_text','text':json.dumps({'answer':'오늘 수업과 할 일을 확인했습니다.','used_fact_ids':['call_1.briefing']})}]}])]
        requests=[]
        def handler(request):
            requests.append(json.loads(request.content))
            return httpx.Response(200,json=packets.pop(0))
        with httpx.Client(transport=httpx.MockTransport(handler)) as client:
            ai=AnalysisAI(Gateway(Settings('fake','synthetic',2),client=client))
            result=ai.run(self.load(),'오늘 할 일 알려줘',{},services={'get_daily_briefing':lambda **kw:{
                'kind':'briefing','date':'2026-10-23','classes':[{'course_name':'합성 수업','starts_at':'09:00','ends_at':'10:00','location':'강의실','private':'never-send'}],
                'tasks':[{'title':'합성 할 일','planned_on':'2026-10-23','due_on':None,'due_time':None,'status':'todo','description':'never-send'}],
                'weather':{'status':'not_configured','location':'춘천'},'secret':'never-send'}})
        self.assertEqual(result['results'][0]['tool'],'get_daily_briefing')
        self.assertNotIn('never-send',json.dumps(requests))
        self.assertIn('call_1.briefing',json.dumps(requests))

    def test_preview_is_explicit_synthetic_and_never_loads_db_or_model(self):
        from backend.app import create_app
        with (patch('backend.planner_api.DatabaseSettings.load',side_effect=AssertionError('DB access')),
              patch('backend.ai.Gateway.send',side_effect=AssertionError('paid request')),
              patch('backend.weather.WeatherService.get',side_effect=AssertionError('weather network')),
              TestClient(create_app(self.package),base_url='http://127.0.0.1') as client):
            packet=client.get('/api/briefing/preview').json()
            self.assertEqual(packet['kind'],'briefing')
            self.assertTrue(packet['preview'])
            self.assertEqual(len(packet['classes']),3)
            self.assertEqual(len(packet['tasks']),3)
