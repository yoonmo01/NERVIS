import unittest
from datetime import date, datetime, time
from zoneinfo import ZoneInfo
from backend.briefing import task_group, preview_briefing, briefing_facts


class TaskGroupTests(unittest.TestCase):
    def test_deadline_boundaries_planned_dates_and_unscheduled(self):
        now = datetime(2026, 10, 24, 12, tzinfo=ZoneInfo('Asia/Seoul'))
        day = now.date()
        cases = [({'due_on': date(2026,10,23)}, 'overdue'),
                 ({'due_on': day, 'due_time': time(11,59)}, 'overdue'),
                 ({'due_on': day, 'due_time': time(12)}, 'today'),
                 ({'due_on': day}, 'today'),
                 ({'planned_on': day, 'due_on':date(2026,10,29)}, 'today'),
                 ({'planned_on':date(2026,10,23)}, 'remaining'),
                 ({'due_on':date(2026,10,29)}, 'remaining'), ({}, 'remaining')]
        for row, expected in cases:
            self.assertEqual(task_group(row,day,now),expected)
        self.assertEqual(task_group({'due_on':date(2026,10,25),'due_time':time(1)},date(2026,10,25),now),'today')

    def test_preview_and_model_share_group_labels(self):
        value=preview_briefing()
        self.assertEqual({t['task_group'] for t in value['tasks']},{'overdue','today','remaining'})
        facts=briefing_facts('get_daily_briefing',value,'c')['facts']['c.briefing']
        self.assertEqual(facts['task_group_counts'],{'overdue':1,'today':1,'remaining':1})
        self.assertTrue(all('task_group' in row for row in facts['tasks']))
