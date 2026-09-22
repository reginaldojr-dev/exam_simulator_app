from __future__ import annotations

from pathlib import Path

from exam_trainer.adapters.exercise_definition.json_loader import JsonExerciseDefinitionLoader
from exam_trainer.adapters.pack.json_pack_loader import JsonPackLoader
from exam_trainer.application.mvp_models import ExerciseRef
from exam_trainer.domain.pack_definition import PackDefinition


class LocalPackCatalog:
    def __init__(
        self,
        managed_packs_dir: Path,
        bundled_packs_dir: Path | None = None,
        pack_loader: JsonPackLoader | None = None,
        exercise_loader: JsonExerciseDefinitionLoader | None = None,
    ) -> None:
        self._managed_packs_dir = managed_packs_dir
        self._bundled_packs_dir = bundled_packs_dir
        self._pack_loader = pack_loader or JsonPackLoader()
        self._exercise_loader = exercise_loader or JsonExerciseDefinitionLoader()

    def list_packs(self) -> list[PackDefinition]:
        packs: dict[str, PackDefinition] = {}
        for root in self._pack_roots():
            pack_json = root / "pack.json"
            if pack_json.is_file():
                pack = self._pack_loader.load(pack_json)
                packs[pack.id] = pack
        return sorted(packs.values(), key=lambda pack: pack.name.lower())

    def list_exercises(self, pack_id: str) -> list[ExerciseRef]:
        for root in self._pack_roots():
            pack_json = root / "pack.json"
            if not pack_json.is_file():
                continue
            pack = self._pack_loader.load(pack_json)
            if pack.id != pack_id:
                continue
            return self._exercise_refs(root, pack)
        return []

    def _exercise_refs(self, pack_root: Path, pack: PackDefinition) -> list[ExerciseRef]:
        refs: list[ExerciseRef] = []
        for level in pack.levels:
            level_path = pack_root / level.path
            for exercise_json in sorted(level_path.glob("*/exercise.json")):
                definition = self._exercise_loader.load(exercise_json)
                refs.append(
                    ExerciseRef(
                        pack=pack,
                        level_id=level.id,
                        definition=definition,
                        content_path=exercise_json.parent,
                    )
                )
        return refs

    def _pack_roots(self) -> list[Path]:
        roots: list[Path] = []
        for base_dir in (self._bundled_packs_dir, self._managed_packs_dir):
            if base_dir is None or not base_dir.is_dir():
                continue
            roots.extend(child for child in base_dir.iterdir() if child.is_dir())
        return roots
