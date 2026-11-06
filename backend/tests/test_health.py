import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from backend.prediction_store import PredictionStore


class PredictionStorePingTests(unittest.TestCase):
    def test_ping_reports_sqlite_when_no_database_url(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            store = PredictionStore(sqlite_path=str(Path(temp_dir) / "predictions.db"))
            with patch.object(store, "_database_url_value", return_value=None):
                result = store.ping()

        self.assertEqual(result["engine"], "sqlite")
        self.assertFalse(result["configured"])
        self.assertTrue(result["connected"])
        self.assertIsNone(result["error"])
        self.assertGreaterEqual(result["latency_ms"], 0)

    def test_ping_reports_postgres_outage_without_raising(self):
        store = PredictionStore(database_url="postgresql://u:p@127.0.0.1:1/none")
        with patch.object(store, "_connect_pg", side_effect=RuntimeError("connection refused")):
            result = store.ping()

        self.assertEqual(result["engine"], "postgresql")
        self.assertTrue(result["configured"])
        self.assertFalse(result["connected"])
        self.assertEqual(result["error"], "connection refused")


if __name__ == "__main__":
    unittest.main()
