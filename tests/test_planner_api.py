"""Real PostgreSQL integration in a disposable synthetic-only database; explicit opt-in."""
import os
from datetime import datetime
from zoneinfo import ZoneInfo
from pathlib import Path
import unittest
from uuid import uuid4

from fastapi.testclient import TestClient
from test_analysis import PackageCase


@unittest.skipUnless(os.environ.get('NERVIS_RUN_DB_TESTS') == '1', 'explicit local DB integration opt-in')
class PlannerApiTests(PackageCase):
    @classmethod
    def setUpClass(cls):
        from backend.planner import DatabaseSettings, PlannerStore
        from psycopg import sql
        cls.settings = DatabaseSettings.load()
        cls.database = 'nervis_test_' + uuid4().hex
        with cls.settings.connect(autocommit=True) as conn:
            conn.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(cls.database)))
        from dataclasses import replace
        cls.store = PlannerStore(replace(cls.settings, dbname=cls.database))
        try:
            with cls.store.settings.connect() as conn:
                for migration in sorted(Path('database/migrations').glob('*.sql')):
                    conn.execute(migration.read_text(encoding='utf-8'))
        except BaseException:
            cls.tearDownClass()
            raise

    @classmethod
    def tearDownClass(cls):
        from psycopg import sql
        with cls.settings.connect(autocommit=True) as conn:
            conn.execute(sql.SQL('DROP DATABASE {}').format(sql.Identifier(cls.database)))

    def setUp(self):
        super().setUp()
        from backend.app import create_app
        from backend.weather import WeatherService
        with self.store.settings.connect() as conn:
            conn.execute('TRUNCATE api_requests, tasks, class_meetings, courses RESTART IDENTITY')
        self.client = self.enterContext(TestClient(create_app(self.package, planner_store=self.store, weather_service=WeatherService('',clock=lambda:datetime(2026,10,23,12,tzinfo=ZoneInfo('Asia/Seoul')))),
                                                   base_url='http://127.0.0.1'))

    def post(self, path, body, key=None):
        return self.client.post(path, json=body, headers={'Idempotency-Key': str(key or uuid4())})

    def course(self):
        result = self.post('/api/courses', {'name': '합성 수업', 'semester_name': '합성 학기',
                           'starts_on': '2026-09-01', 'ends_on': '2026-12-31'})
        self.assertEqual(result.status_code, 201, result.text)
        return result.json()

    def test_course_meeting_and_task_crud(self):
        course = self.course(); cid = course['id']
        meeting = self.post(f'/api/courses/{cid}/meetings', {'weekday': 5, 'starts_at': '09:00',
                             'ends_at': '10:00', 'location': '합성 강의실'})
        self.assertEqual(meeting.status_code, 201, meeting.text)
        mid = meeting.json()['id']
        changed = self.client.patch(f'/api/class-meetings/{mid}', json={'location': '변경'})
        self.assertEqual(changed.json()['location'], '변경')
        self.assertEqual(len(self.client.get(f'/api/courses/{cid}/meetings').json()), 1)
        self.assertEqual(self.client.get(f'/api/courses/{cid}/meetings?limit=0').status_code, 422)
        self.assertEqual(self.client.get(f'/api/courses/{cid}/meetings?offset=1').json(), [])
        self.assertEqual(self.client.patch(f'/api/courses/{cid}', json={'name': '수정'}).json()['name'], '수정')
        task = self.post('/api/tasks', {'title': "합성 보고서 '); DROP TABLE courses; --", 'course_id': cid,
                         'planned_on': '2026-10-23', 'due_on': '2026-10-24', 'due_time': '18:00'})
        self.assertEqual(task.status_code, 201, task.text)
        tid = task.json()['id']
        done = self.client.patch(f'/api/tasks/{tid}', json={'status': 'done'})
        self.assertIsNotNone(done.json()['completed_at'])
        reopened = self.client.patch(f'/api/tasks/{tid}', json={'status': 'todo'})
        self.assertIsNone(reopened.json()['completed_at'])
        self.assertEqual(self.client.get(f'/api/tasks/{tid}').status_code, 200)
        self.assertEqual(self.client.delete(f'/api/courses/{cid}').status_code, 204)
        self.assertIsNone(self.client.get(f'/api/tasks/{tid}').json()['course_id'])
        self.assertEqual(self.client.get(f'/api/class-meetings/{mid}').status_code, 404)
        self.assertEqual(self.client.delete(f'/api/tasks/{tid}').status_code, 204)
        self.assertEqual(self.client.get(f'/api/tasks/{tid}').status_code, 404)

    def test_batch_atomicity_replay_and_conflict(self):
        cid = self.course()['id']
        bad = self.post('/api/tasks/batch', {'items': [{'title': 'A'}, {'title': 'B', 'course_id': 99999}]})
        self.assertEqual(bad.status_code, 422, bad.text)
        self.assertEqual(self.client.get('/api/tasks').json(), [])

        key = uuid4(); body = {'items': [{'title': 'A'}, {'title': 'B', 'course_id': cid}]}
        first = self.post('/api/tasks/batch', body, key)
        self.assertEqual(first.status_code, 201, first.text)
        self.assertEqual(self.post('/api/tasks/batch', body, key).json(), first.json())
        self.assertEqual(len(self.client.get('/api/tasks').json()), 2)
        self.assertEqual(self.post('/api/tasks/batch', {'items': [{'title': 'changed'}]}, key).status_code, 409)
        self.assertEqual(self.post('/api/tasks', {'title': 'A'}, key).status_code, 409)

    def test_database_outage_does_not_break_analysis_or_leak_details(self):
        import psycopg
        from unittest.mock import patch
        with patch('backend.planner.psycopg.connect', side_effect=psycopg.OperationalError('secret-connection-details')):
            result = self.client.get('/api/tasks')
            self.assertEqual(result.status_code, 503)
            self.assertNotIn('secret-connection-details', result.text)
            self.assertEqual(self.client.get('/api/health').status_code, 200)

    def test_validated_inputs_patch_merge_and_no_input_echo(self):
        invalid = [{'title': ' '}, {'title': 'x', 'due_time': '18:00'}, {'title': 'x', 'due_on': '2026-02-30'},
                   {'title': 'x', 'course_id': True}, {'title': 'x', 'planned_on': 123},
                   {'title': 'x', 'status': 'done'}, {'title': 'x', 'extra': 'secret-never-echo'}]
        for body in invalid:
            result = self.post('/api/tasks', body)
            self.assertEqual(result.status_code, 422, result.text)
            self.assertNotIn('secret-never-echo', result.text)
        cid = self.course()['id']
        self.assertEqual(self.client.patch(f'/api/courses/{cid}', json={'ends_on': '2026-08-01'}).status_code, 422)
        self.assertEqual(self.client.patch(f'/api/courses/{cid}', json={'name': None}).status_code, 422)
        self.assertEqual(self.client.patch(f'/api/courses/{cid}', json={}).status_code, 422)
        self.assertEqual(self.post('/api/courses/99999/meetings', {'weekday': 1, 'starts_at': '10:00', 'ends_at': '09:00'}).status_code, 422)
        self.assertEqual(self.client.get('/api/tasks?limit=100000').status_code, 422)
        self.assertEqual(self.client.get('/api/tasks?course_id=999999999999999999999999999999').status_code, 422)

    def test_daily_briefing_filters_date_weekday_status_and_location(self):
        cid = self.course()['id']
        self.post(f'/api/courses/{cid}/meetings', {'weekday': 5, 'starts_at': '09:00', 'ends_at': '10:00'})
        for title, planned, due in [('today', '2026-10-23', None), ('unfinished_yesterday', '2026-10-22', None), ('overdue', None, '2026-10-22'),
                                     ('future', '2026-10-25', '2026-10-25')]:
            self.post('/api/tasks', {'title': title, 'planned_on': planned, 'due_on': due})
        done = self.post('/api/tasks', {'title': 'done', 'planned_on': '2026-10-23'}).json()
        self.client.patch(f"/api/tasks/{done['id']}", json={'status': 'done'})
        response = self.client.get('/api/briefing?date=2026-10-23').json()
        self.assertEqual(response['date'], '2026-10-23')
        self.assertEqual(len(response['classes']), 1)
        self.assertEqual({r['title'] for r in response['tasks']}, {'today', 'overdue', 'unfinished_yesterday','future'})
        self.assertEqual({r['title']:r['task_group'] for r in response['tasks']},
                         {'today':'today','overdue':'overdue','unfinished_yesterday':'remaining','future':'remaining'})
        self.assertEqual(response['weather']['location'], '춘천')
        self.assertEqual(response['weather']['status'], 'not_configured')
        self.assertEqual(self.client.get('/api/briefing?date=2027-01-01').json()['classes'], [])
        self.assertEqual(self.client.get('/api/briefing?location=서울').json()['weather']['location'], '서울')

    def test_origin_and_required_idempotency_header(self):
        result = self.client.post('/api/tasks', json={'title': 'x'})
        self.assertEqual(result.status_code, 422)
        result = self.client.post('/api/tasks', json={'title': 'x'}, headers={
            'Origin': 'https://evil.example', 'Idempotency-Key': str(uuid4())})
        self.assertEqual(result.status_code, 403)
        for method in ['PATCH', 'DELETE']:
            result = self.client.options('/api/tasks/1', headers={'Origin': 'http://127.0.0.1:5173',
                'Access-Control-Request-Method': method, 'Access-Control-Request-Headers': 'Content-Type,Idempotency-Key'})
            self.assertEqual(result.status_code, 200)
        self.assertEqual(self.client.get('/api/tasks').json(), [])

    def test_db_status_and_concurrent_idempotency(self):
        from concurrent.futures import ThreadPoolExecutor
        from backend.planner_schemas import TaskCreate
        self.assertEqual(self.client.get('/api/db/status').json()['status'], 'ok')
        key = uuid4(); body = TaskCreate(title='concurrent')
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: self.store.create_task(body, key), range(2)))
        self.assertEqual(results[0], results[1])
        self.assertEqual(len(self.client.get('/api/tasks').json()), 1)
