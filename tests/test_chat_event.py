"""Synthetic serialization regression; execution deferred by user request."""
from datetime import date, time, datetime, timezone
from decimal import Decimal
import json
import unittest
from uuid import UUID

from backend.app import encode_chat_event


class ChatEventTests(unittest.TestCase):
    def test_stream_encodes_course_times_and_dates_like_normal_json_response(self):
        frame = encode_chat_event({'type': 'result', 'request_id': UUID(int=1),
            'reply': {'meeting': {'starts_at': time(9), 'ends_at': time(11)},
                      'starts_on': date(2026, 9, 1), 'created_at': datetime(2026, 10, 29, tzinfo=timezone.utc),
                      'value': Decimal('1.5')}})
        self.assertTrue(frame.endswith('\n\n'))
        event = json.loads(frame.removeprefix('data: '))
        self.assertEqual(event['reply']['meeting'], {'starts_at': '09:00:00', 'ends_at': '11:00:00'})
        self.assertEqual(event['reply']['starts_on'], '2026-09-01')
        self.assertEqual(event['request_id'], str(UUID(int=1)))
        self.assertEqual(event['reply']['value'], 1.5)

    def test_nonfinite_result_does_not_escape_as_invalid_json(self):
        with self.assertRaises(ValueError):
            encode_chat_event({'type': 'result', 'reply': {'value': float('nan')}})
