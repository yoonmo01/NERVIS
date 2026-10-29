"""Synthetic contracts; execution deferred at the user's request."""
import json
import unittest

from backend.ai import AIError, _explanation, explanation_format
from backend.response_text import result_narration


class ResponseTextTests(unittest.TestCase):
    def test_explanation_schema_limits_fact_ids_and_diagnostics_distinguish_failures(self):
        schema = explanation_format({'call.briefing'})['format']['schema']
        self.assertFalse(schema['additionalProperties'])
        self.assertEqual(schema['properties']['used_fact_ids']['items']['enum'], ['call.briefing'])
        cases = [('설명만 반환', 'invalid_json'),
                 (json.dumps({'answer': '설명'}), 'invalid_fields'),
                 (json.dumps({'answer': '설명', 'used_fact_ids': []}), 'missing_fact_ids'),
                 (json.dumps({'answer': '설명', 'used_fact_ids': ['other']}), 'unknown_fact_ids'),
                 (json.dumps({'answer': '설명', 'used_fact_ids': ['call.briefing', 'call.briefing']}), 'duplicate_fact_ids')]
        for text, reason in cases:
            with self.subTest(reason=reason), self.assertRaises(AIError) as caught:
                _explanation([{'type': 'message', 'content': [{'type': 'output_text', 'text': text}]}], {'call.briefing'})
            self.assertEqual(caught.exception.reason, reason)

    def test_fallback_uses_real_groups_and_does_not_invent_unavailable_schedules(self):
        result = {'tool': 'get_daily_briefing', 'data': {'date': '2026-10-28', 'classes': [],
                  'tasks': [{'title': '합성 보고서', 'status': 'todo', 'task_group': 'remaining'}],
                  'weather': {'location': '춘천', 'current': None}}}
        text = result_narration([result])
        self.assertIn('합성 보고서', text)
        self.assertIn('남은 할 일은 1개', text)
        self.assertNotIn('해당 날짜 할 일은 1개', text)
        result['data']['calendar_status'] = 'unavailable'
        text = result_narration([result])
        self.assertIn('수업과 할 일은 조회하지 못했습니다', text)
        self.assertNotIn('합성 보고서', text)
        self.assertLessEqual(len(text), 2000)
