"""Tool contracts only; no external requests or database access."""
import unittest
from backend.ai import TOOLS, TOOL_MODELS
from pydantic import ValidationError


class BriefingToolContractTests(unittest.TestCase):
    def test_read_tools_are_strict_with_nullable_required_fields(self):
        for name in ('get_daily_briefing', 'get_weather'):
            tool = next(tool for tool in TOOLS if tool['name'] == name)
            self.assertTrue(tool['strict'])
            schema = tool['parameters']
            self.assertFalse(schema['additionalProperties'])
            self.assertEqual(set(schema['required']), {'date', 'location'})
            self.assertEqual(TOOL_MODELS[name](date=None, location=None).model_dump(), {'date': None, 'location': None})

    def test_strict_contract_does_not_weaken_server_validation(self):
        for fields in ({'date': 'today'}, {'date': '2026-02-30'}, {'location': ''}, {'unexpected': 'private'}):
            with self.assertRaises(ValidationError):
                TOOL_MODELS['get_daily_briefing'](**fields)
