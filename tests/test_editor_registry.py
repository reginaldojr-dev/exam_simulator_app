"""Fase 4: EditorRegistry is the single source of truth for known editor
presets -- both the Settings combo and automatic detection read from it.
Covered independently of the Qt-dependent main_window tests."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from exam_trainer.adapters.editor.editor_registry import (
    EDITOR_REGISTRY,
    DuplicateEditorError,
    EditorPreset,
    EditorRegistry,
    default_editor_registry,
)
from exam_trainer.adapters.editor.subprocess_editor import (
    SubprocessEditorFactory,
    resolve_known_editor,
)


class EditorRegistryTest(unittest.TestCase):
    def test_contains_the_current_known_editors(self) -> None:
        self.assertEqual(EDITOR_REGISTRY.ids(), ("VS Code", "Zed", "Cursor"))

    def test_lookup_by_id_works(self) -> None:
        preset = EDITOR_REGISTRY.get("VS Code")
        self.assertIsNotNone(preset)
        self.assertEqual(preset.id, "VS Code")
        self.assertEqual(preset.candidates, ("code", "Code.exe"))
        self.assertIsNone(EDITOR_REGISTRY.get("does-not-exist"))

    def test_find_is_case_insensitive_like_resolution_was_before_the_registry(self) -> None:
        self.assertEqual(EDITOR_REGISTRY.find("vs code").id, "VS Code")
        self.assertEqual(EDITOR_REGISTRY.find("ZED").id, "Zed")
        self.assertEqual(EDITOR_REGISTRY.find("Cursor").id, "Cursor")
        self.assertIsNone(EDITOR_REGISTRY.find("totally-custom-binary"))

    def test_listing_is_deterministic(self) -> None:
        first = EDITOR_REGISTRY.ids()
        second = EDITOR_REGISTRY.ids()
        self.assertEqual(first, second)
        self.assertEqual(tuple(preset.id for preset in EDITOR_REGISTRY.presets()), first)

    def test_duplicate_id_is_rejected(self) -> None:
        registry = EditorRegistry((EditorPreset(id="VS Code", candidates=("code",)),))
        with self.assertRaises(DuplicateEditorError):
            registry.register(EditorPreset(id="VS Code", candidates=("code",)))
        # The failed registration did not corrupt the existing entry.
        self.assertEqual(registry.get("VS Code").candidates, ("code",))

    def test_default_registry_matches_the_shared_singleton(self) -> None:
        # default_editor_registry() is the factory EDITOR_REGISTRY itself is
        # built from; both must agree, so there is only one real data source.
        self.assertEqual(default_editor_registry().ids(), EDITOR_REGISTRY.ids())


class SubprocessEditorFactoryKnownLabelsTest(unittest.TestCase):
    def test_known_labels_is_the_registry_source(self) -> None:
        factory = SubprocessEditorFactory()
        self.assertEqual(factory.known_labels(), EDITOR_REGISTRY.ids())


class ResolveKnownEditorTest(unittest.TestCase):
    """resolve_known_editor is the auto-detection side; it must read candidate
    executables from the same EditorRegistry the combo/factory use, and keep
    behaving exactly as it did before the registry existed."""

    def test_tries_each_registry_candidate_in_order_until_one_resolves(self) -> None:
        calls: list[str] = []

        def fake_which(command: str) -> str | None:
            calls.append(command)
            return "/usr/bin/code" if command == "Code.exe" else None

        with patch("exam_trainer.adapters.editor.subprocess_editor.shutil.which", side_effect=fake_which), \
             patch("exam_trainer.adapters.editor.subprocess_editor.Path.is_file", return_value=True):
            resolved = resolve_known_editor("VS Code")

        self.assertEqual(resolved, "/usr/bin/code")
        self.assertEqual(calls, ["code", "Code.exe"])

    def test_lookup_is_case_insensitive(self) -> None:
        with patch("exam_trainer.adapters.editor.subprocess_editor.shutil.which", return_value="/usr/bin/zed"), \
             patch("exam_trainer.adapters.editor.subprocess_editor.Path.is_file", return_value=True):
            self.assertEqual(resolve_known_editor("zed"), "/usr/bin/zed")
            self.assertEqual(resolve_known_editor("ZED"), "/usr/bin/zed")

    def test_unknown_label_falls_back_to_trying_the_label_itself_as_a_command(self) -> None:
        # Preserves the pre-registry fallback: an arbitrary label that is not a
        # known preset is still tried verbatim as a single candidate command.
        with patch("exam_trainer.adapters.editor.subprocess_editor.shutil.which", return_value=None) as which:
            self.assertIsNone(resolve_known_editor("some-custom-editor"))
            which.assert_called_once_with("some-custom-editor")

    def test_returns_none_when_nothing_resolves(self) -> None:
        with patch("exam_trainer.adapters.editor.subprocess_editor.shutil.which", return_value=None):
            self.assertIsNone(resolve_known_editor("Cursor"))


if __name__ == "__main__":
    unittest.main()
