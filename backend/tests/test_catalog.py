"""Search must work from the shipped lite catalog when the full data/movies.db is absent (e.g. on Vercel)."""
import os
import tempfile
import unittest
from unittest import mock

import backend.main as api


class LiteCatalogTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        patches = [
            mock.patch.object(api, "DB_PATH", os.path.join(self.tmp.name, "missing.db")),
            mock.patch.object(api, "_catalog_path_cache", None),
            mock.patch("tempfile.gettempdir", return_value=self.tmp.name),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)
        self.addCleanup(self.tmp.cleanup)

    def test_lite_catalog_is_shipped(self):
        self.assertTrue(os.path.exists(api.LITE_CATALOG_GZ))

    def test_search_falls_back_to_lite_catalog(self):
        path = api.catalog_db_path()
        self.assertEqual(path, os.path.join(self.tmp.name, "movies_lite.db"))
        titles = [m["title"] for m in api.search_movies_from_db("stalker", 5)]
        self.assertIn("Stalker", titles)

    def test_status_reports_lite_source(self):
        status = api.dataset_status()
        self.assertTrue(status["database_indexed"])
        self.assertEqual(status["catalog_source"], "lite")
        self.assertGreater(status["catalog_entries_count"], 10_000)


if __name__ == "__main__":
    unittest.main()
