import unittest
from datetime import date
from backend.course_tools import semester_defaults


class SemesterTests(unittest.TestCase):
    def test_fixed_inclusive_sixteen_weeks_and_current_year(self):
        for name, start, end in [('1학기','2026-03-01','2026-06-20'),('2학기','2026-09-01','2026-12-21'),
                                 ('2028년 1학기','2028-03-01','2028-06-20'),('2027-2','2027-09-01','2027-12-21')]:
            result=semester_defaults({'semester_name':name},date(2026,10,24))
            self.assertEqual(result['starts_on'],start)
            self.assertEqual(result['ends_on'],end)
            self.assertEqual((date.fromisoformat(end)-date.fromisoformat(start)).days+1,112)

    def test_explicit_dates_and_other_semesters_are_preserved(self):
        draft={'semester_name':'1학기','starts_on':'2026-03-05','ends_on':'2026-06-30'}
        result=semester_defaults(draft,date(2026,10,24))
        self.assertEqual(result['starts_on'],draft['starts_on'])
        self.assertEqual(result['ends_on'],draft['ends_on'])
        self.assertEqual(draft['semester_name'],'1학기')
        self.assertEqual(semester_defaults({'semester_name':'여름 계절학기'},date(2026,10,24)),{'semester_name':'여름 계절학기'})
