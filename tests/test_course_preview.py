"""Pure preview contracts; execution deferred at the user's request."""
import unittest
from backend.course_tools import CourseRequest, course_preview, course_preview_requested


class CoursePreviewTests(unittest.TestCase):
    def test_explicit_before_registration_request_is_preview_only(self):
        self.assertTrue(course_preview_requested('등록하기 전에 지금 어떻게 등록할 건지 먼저 말해줄래'))
        self.assertFalse(course_preview_requested('확인했어. 그대로 등록해 줘'))
        self.assertFalse(course_preview_requested('전에 등록한 수업을 알려 줘'))
        request = CourseRequest.model_validate({'mode': 'apply', 'courses': [{'name': '합성 수업',
            'meetings': [{'weekday': 1, 'starts_at': '09:00', 'ends_at': '11:00', 'location': '합성 강의실'}]}]})
        receipt = course_preview(request)
        self.assertEqual(receipt['status'], 'no_change')
        self.assertEqual(receipt['items'], [])
        self.assertIn('아직 저장하지 않았습니다', receipt['message'])
        self.assertIn('월요일', receipt['message'])
        self.assertIn('학기와 적용 기간', receipt['message'])
