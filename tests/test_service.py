import unittest
import json
import os
import sys

# Ensure root workspace is on path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from service.main import validate_output, VALID_INTENTS, VALID_KEYS


class TestInferenceService(unittest.TestCase):

    def test_schema_validation_valid(self):
        """Test that valid 4-key JSON conforming to schema passes validation."""
        valid_sample = {
            "intent": "alarm_set",
            "date": "tomorrow",
            "time": "seven thirty am",
            "place": None
        }
        res = validate_output(json.dumps(valid_sample))
        self.assertIsNotNone(res)
        self.assertEqual(res["intent"], "alarm_set")
        self.assertEqual(res["date"], "tomorrow")
        self.assertEqual(res["time"], "seven thirty am")
        self.assertIsNone(res["place"])

    def test_schema_validation_invalid_intent(self):
        """Test that invalid intent is rejected."""
        invalid_intent = {
            "intent": "play_music",  # Not in allowed 8 intents
            "date": None,
            "time": None,
            "place": None
        }
        res = validate_output(json.dumps(invalid_intent))
        self.assertIsNone(res)

    def test_schema_validation_missing_key(self):
        """Test that JSON missing required keys is rejected."""
        missing_key = {
            "intent": "weather_query",
            "date": None,
            "time": None
            # missing "place"
        }
        res = validate_output(json.dumps(missing_key))
        self.assertIsNone(res)

    def test_schema_validation_extra_key(self):
        """Test that JSON with unexpected extra keys is rejected."""
        extra_key = {
            "intent": "weather_query",
            "date": None,
            "time": None,
            "place": "london",
            "confidence": 0.99  # Extra forbidden key
        }
        res = validate_output(json.dumps(extra_key))
        self.assertIsNone(res)

    def test_schema_validation_non_json_string(self):
        """Test that non-JSON text (such as FAULT_INJECT 'not json') fails validation."""
        res = validate_output("not json")
        self.assertIsNone(res)

    def test_all_eight_intents_allowed(self):
        """Verify all eight specification intents are recognized."""
        expected = {
            "alarm_set", "alarm_query", "calendar_set", "calendar_query",
            "calendar_remove", "weather_query", "datetime_query", "recommendation_events"
        }
        self.assertEqual(VALID_INTENTS, expected)


if __name__ == "__main__":
    unittest.main()
