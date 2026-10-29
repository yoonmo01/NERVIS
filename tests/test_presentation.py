import unittest
from backend.presentation import presentation_targets, checked_segments


class PresentationTests(unittest.TestCase):
    def test_only_current_result_targets_and_exact_answer_are_accepted(self):
        results = [{'tool': 'get_daily_briefing', 'data': {'classes': [{}], 'tasks': [{}, {}]}}]
        targets = presentation_targets(results)
        self.assertIn('r0.tasks.1', targets)
        segments = [{'text': '먼저 할 일을 보세요.', 'target': 'r0.tasks.1'}]
        self.assertEqual(checked_segments(segments, '먼저 할 일을 보세요.', results), segments)
        for value in ([{'text': '다른 문장', 'target': 'r0.tasks.1'}],
                      [{'text': '먼저 할 일을 보세요.', 'target': 'r0.tasks.2'}],
                      [{'text': '먼저 할 일을 보세요.', 'target': '__proto__'}], 'invalid'):
            self.assertEqual(checked_segments(value, '먼저 할 일을 보세요.', results), [])

    def test_task_targets_do_not_expose_database_ids(self):
        self.assertEqual(presentation_targets([{'tool': 'list_tasks', 'data': {'items': [{'id': 987}]}}]),
                         ['response', 'r0.tasks', 'r0.tasks.0'])

    def test_only_rendered_results_and_visible_briefing_rows_get_targets(self):
        task = {'tool': 'list_tasks', 'data': {'items': [{}]}}
        self.assertNotIn('r1.tasks.0', presentation_targets([task, task]))
        weather = {'tool': 'get_weather', 'data': {}}
        daily = {'tool': 'get_daily_briefing', 'data': {'classes': [], 'tasks': [{'status': 'done'}, {'status': 'todo'}]}}
        targets = presentation_targets([weather, daily])
        self.assertNotIn('r0.weather', targets)
        self.assertNotIn('r1.tasks.0', targets)
        self.assertIn('r1.tasks.1', targets)
        self.assertNotIn('r0.weather', presentation_targets([weather, {'tool': 'analyze_region', 'data': {}}]))
