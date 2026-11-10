"""The root requirements.txt (Vercel) must list the same packages as backend/requirements.txt (Docker, CI)."""
import os
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _requirements(path):
    with open(path) as f:
        lines = (line.split("#", 1)[0].strip() for line in f)
        return sorted(line.replace(" ", "") for line in lines if line)


class RequirementsInSyncTest(unittest.TestCase):
    def test_root_matches_backend(self):
        self.assertEqual(
            _requirements(os.path.join(ROOT, "requirements.txt")),
            _requirements(os.path.join(ROOT, "backend", "requirements.txt")),
        )

    def test_root_has_no_includes(self):
        # Vercel's requirements parser cannot follow "-r" / "-c" includes.
        self.assertFalse(any(r.startswith("-") for r in _requirements(os.path.join(ROOT, "requirements.txt"))))


if __name__ == "__main__":
    unittest.main()
