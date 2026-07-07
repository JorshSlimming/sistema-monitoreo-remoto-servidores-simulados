"""Repository hygiene checks for the final PSK-secured protocol."""

from pathlib import Path
import unittest


PROJECT_ROOT = Path(__file__).resolve().parent.parent


class RepoCleanupTests(unittest.TestCase):
    def test_no_removed_crypto_artifacts_or_local_paths_remain(self) -> None:
        forbidden = (
            "cryptography",
            "auth_handler",
            "psk_config",
            "/home/maxi",
        )
        checked_suffixes = {".py", ".md", ".txt", ".json", ".sh", ".ps1"}
        ignored_dirs = {".git", "__pycache__", "data", "logs", "artifacts", "captures"}
        hits: list[str] = []

        for path in PROJECT_ROOT.rglob("*"):
            if any(part in ignored_dirs for part in path.parts):
                continue
            if path.name == "test_repo_cleanup.py":
                continue
            if not path.is_file() or path.suffix not in checked_suffixes:
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            for token in forbidden:
                if token in text:
                    hits.append(f"{path.relative_to(PROJECT_ROOT)} contains {token}")

        self.assertEqual(hits, [])


if __name__ == "__main__":
    unittest.main()
