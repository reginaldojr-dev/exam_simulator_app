"""Fase 6: validates `enabled_plugins` persistence in `JsonAppConfigRepository`.

Plugins are disabled by default and opting one in must never break an old
config file that predates this field.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from rankeddojo.adapters.persistence.json_app_config_repository import JsonAppConfigRepository


class EnabledPluginsDefaultTest(unittest.TestCase):
    def test_no_config_file_at_all_defaults_to_empty_tuple(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = JsonAppConfigRepository(Path(tmp) / "config.json")
            self.assertEqual(repo.load_enabled_plugins(), ())

    def test_old_config_without_enabled_plugins_key_still_loads(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config_path = Path(tmp) / "config.json"
            config_path.write_text(
                json.dumps({"editor_command": "code", "ui_locale": "pt-BR"}),
                encoding="utf-8",
            )
            repo = JsonAppConfigRepository(config_path)

            self.assertEqual(repo.load_enabled_plugins(), ())
            # Unrelated existing fields are still readable: adding this field
            # never migrates or touches the rest of an old config file.
            self.assertEqual(repo.load_editor_command(), "code")
            self.assertEqual(repo.load_ui_locale(), "pt-BR")

    def test_malformed_enabled_plugins_value_defaults_to_empty_tuple(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config_path = Path(tmp) / "config.json"
            config_path.write_text(json.dumps({"enabled_plugins": "not-a-list"}), encoding="utf-8")
            repo = JsonAppConfigRepository(config_path)

            self.assertEqual(repo.load_enabled_plugins(), ())


class EnabledPluginsRoundTripTest(unittest.TestCase):
    def test_save_then_load_round_trips(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = JsonAppConfigRepository(Path(tmp) / "config.json")

            repo.save_enabled_plugins(("plugin-a", "plugin-b"))

            self.assertEqual(repo.load_enabled_plugins(), ("plugin-a", "plugin-b"))

    def test_save_deduplicates_preserving_order(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = JsonAppConfigRepository(Path(tmp) / "config.json")

            repo.save_enabled_plugins(("plugin-a", "plugin-b", "plugin-a"))

            self.assertEqual(repo.load_enabled_plugins(), ("plugin-a", "plugin-b"))

    def test_save_empty_tuple_clears_it(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = JsonAppConfigRepository(Path(tmp) / "config.json")
            repo.save_enabled_plugins(("plugin-a",))

            repo.save_enabled_plugins(())

            self.assertEqual(repo.load_enabled_plugins(), ())

    def test_saving_enabled_plugins_preserves_other_existing_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config_path = Path(tmp) / "config.json"
            repo = JsonAppConfigRepository(config_path)
            repo.save_editor_command("zed")

            repo.save_enabled_plugins(("plugin-a",))

            self.assertEqual(repo.load_editor_command(), "zed")
            self.assertEqual(repo.load_enabled_plugins(), ("plugin-a",))


if __name__ == "__main__":
    unittest.main()
