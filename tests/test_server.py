"""Tests for server.py helpers and validation."""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))


class TestGetApiKey(unittest.TestCase):
    def test_env_var_priority(self):
        """Env var should take priority over config.json."""
        from server import get_api_key
        with patch.dict(os.environ, {"TMDB_API_KEY": "env_key_123"}):
            with patch("server.load_config", return_value={"tmdb_api_key": "config_key"}):
                self.assertEqual(get_api_key(), "env_key_123")

    def test_fallback_to_config(self):
        """Should fall back to config.json when no env var."""
        from server import get_api_key
        with patch.dict(os.environ, {}, clear=True):
            # Remove TMDB_API_KEY if it exists
            os.environ.pop("TMDB_API_KEY", None)
            with patch("server.load_config", return_value={"tmdb_api_key": "from_config"}):
                self.assertEqual(get_api_key(), "from_config")

    def test_empty_when_neither(self):
        """Should return empty string when no key available."""
        from server import get_api_key
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("TMDB_API_KEY", None)
            with patch("server.load_config", return_value={}):
                self.assertEqual(get_api_key(), "")


class TestLoadSaveConfig(unittest.TestCase):
    def test_roundtrip(self):
        from server import CONFIG_PATH
        import server

        with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w") as f:
            tmp_path = Path(f.name)

        try:
            original_path = server.CONFIG_PATH
            server.CONFIG_PATH = tmp_path

            server.save_config({"tmdb_api_key": "test123", "language": "en-US"})
            cfg = server.load_config()
            self.assertEqual(cfg["tmdb_api_key"], "test123")
            self.assertEqual(cfg["language"], "en-US")
        finally:
            server.CONFIG_PATH = original_path
            tmp_path.unlink(missing_ok=True)

    def test_load_missing_file(self):
        import server
        original_path = server.CONFIG_PATH
        try:
            server.CONFIG_PATH = Path("/tmp/nonexistent_sunny_config.json")
            cfg = server.load_config()
            self.assertEqual(cfg, {})
        finally:
            server.CONFIG_PATH = original_path


class TestHistory(unittest.TestCase):
    def test_missing_db_returns_empty(self):
        import server
        original = server.SUNNY_HISTORY
        try:
            server.SUNNY_HISTORY = Path("/tmp/nonexistent_history.sqlite")
            self.assertEqual(server.get_history(), [])
            self.assertEqual(server.get_full_history("test"), [])
        finally:
            server.SUNNY_HISTORY = original


if __name__ == "__main__":
    unittest.main()
