import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from backend.prediction_store import PredictionStore


class PredictionStorePersistenceTests(unittest.TestCase):
    def test_log_writes_prediction_that_history_can_retrieve(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            store = PredictionStore(sqlite_path=str(Path(temp_dir) / "predictions.db"))

            # Keep this test isolated from any DATABASE_URL configured on the host.
            with patch.object(store, "_database_url_value", return_value=None):
                inserted = store.log([{
                    "title": "Arrival",
                    "release_year": 2016,
                    "runtime": 116,
                    "budget": 47000000,
                    "original_language": "en",
                    "genres": ["Drama", "Science Fiction"],
                    "probability": 0.87,
                    "is_popular": True,
                    "model_architecture": "Test MLP",
                    "poster_url": "https://example.com/arrival.jpg",
                }])

                rows = store.history(limit=10)

            self.assertTrue(inserted)
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["title"], "Arrival")
            self.assertEqual(rows[0]["release_year"], 2016)
            self.assertEqual(rows[0]["genres"], "Drama, Science Fiction")
            self.assertEqual(rows[0]["probability"], 0.87)
            self.assertTrue(rows[0]["is_popular"])
            self.assertEqual(rows[0]["model_architecture"], "Test MLP")
            self.assertEqual(rows[0]["poster_url"], "https://example.com/arrival.jpg")


if __name__ == "__main__":
    unittest.main()
