"""Known editor/IDE presets: the single source of truth for which editors the
app offers in Settings > Editor/IDE and tries during automatic detection.

To add a new known preset: add an `EditorPreset` in `default_editor_registry()`
below. No other module needs to change.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass


class DuplicateEditorError(ValueError):
    """Raised when two editor presets are registered under the same id."""


@dataclass(frozen=True)
class EditorPreset:
    """A known editor/IDE preset.

    `id` doubles as the display label shown in the combo and as the i18n key
    used to translate it (e.g. "VS Code") -- this mirrors how presets are
    already used today, so the registry does not invent a separate slug for
    what is already a stable identifier.
    """

    id: str
    candidates: tuple[str, ...]          # executable names tried via shutil.which
    windows_patterns: tuple[str, ...] = ()  # relative paths under common Windows install roots


class EditorRegistry:
    """id -> EditorPreset. The single source of truth for known editors."""

    def __init__(self, presets: Iterable[EditorPreset] = ()) -> None:
        self._presets: dict[str, EditorPreset] = {}
        self._order: list[str] = []
        for preset in presets:
            self.register(preset)

    def register(self, preset: EditorPreset) -> None:
        if preset.id in self._presets:
            raise DuplicateEditorError(f"Editor preset already registered: {preset.id}.")
        self._presets[preset.id] = preset
        self._order.append(preset.id)

    def get(self, preset_id: str) -> EditorPreset | None:
        return self._presets.get(preset_id)

    def find(self, label: str) -> EditorPreset | None:
        """Case-insensitive lookup by label/id, matching how presets were resolved before this registry existed."""
        lowered = label.lower()
        for preset_id in self._order:
            if preset_id.lower() == lowered:
                return self._presets[preset_id]
        return None

    def has(self, preset_id: str) -> bool:
        return preset_id in self._presets

    def ids(self) -> tuple[str, ...]:
        return tuple(self._order)

    def presets(self) -> tuple[EditorPreset, ...]:
        return tuple(self._presets[preset_id] for preset_id in self._order)


def default_editor_registry() -> EditorRegistry:
    return EditorRegistry(
        (
            EditorPreset(
                id="VS Code",
                candidates=("code", "Code.exe"),
                windows_patterns=("Microsoft VS Code/Code.exe", "VS Code/Code.exe"),
            ),
            EditorPreset(
                id="Zed",
                candidates=("zed", "Zed.exe"),
                windows_patterns=("Zed/Zed.exe",),
            ),
            EditorPreset(
                id="Cursor",
                candidates=("cursor", "Cursor.exe"),
                windows_patterns=("Cursor/Cursor.exe",),
            ),
        )
    )


# Single shared instance: the combo (via MVPTrainerCoordinator.known_editor_labels)
# and automatic detection (resolve_known_editor, below) both read from this same
# registry, so the list of known editors is never duplicated.
EDITOR_REGISTRY = default_editor_registry()
