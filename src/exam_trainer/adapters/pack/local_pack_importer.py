from __future__ import annotations

import shutil
import tempfile
import zipfile
from pathlib import Path

from exam_trainer.adapters.exercise_definition.json_loader import (
    ExerciseDefinitionError,
    JsonExerciseDefinitionLoader,
)
from exam_trainer.adapters.pack.json_pack_loader import JsonPackLoader, PackDefinitionError
from exam_trainer.domain.pack_definition import PackDefinition


class PackImportError(ValueError):
    pass


class LocalPackImporter:
    def __init__(
        self,
        managed_packs_dir: Path,
        pack_loader: JsonPackLoader | None = None,
        exercise_loader: JsonExerciseDefinitionLoader | None = None,
    ) -> None:
        self._managed_packs_dir = managed_packs_dir
        self._pack_loader = pack_loader or JsonPackLoader()
        self._exercise_loader = exercise_loader or JsonExerciseDefinitionLoader()

    def import_pack(self, source_path: Path | str) -> PackDefinition:
        source = Path(source_path)
        if not source.exists():
            raise PackImportError(f"Pack source does not exist: {source}")

        with tempfile.TemporaryDirectory() as temp_dir:
            prepared_source = self._prepare_source(source, Path(temp_dir))
            pack = self.validate_pack(prepared_source)
            destination = self._managed_packs_dir / pack.id
            if destination.exists():
                shutil.rmtree(destination)
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(prepared_source, destination)
            return pack

    def validate_pack(self, pack_root: Path) -> PackDefinition:
        try:
            pack = self._pack_loader.load(pack_root / "pack.json")
        except PackDefinitionError as error:
            raise PackImportError(str(error)) from error

        for level in pack.levels:
            level_path = pack_root / level.path
            if not level_path.is_dir():
                raise PackImportError(f"Level path not found: {level.path}")
            exercise_files = list(level_path.glob("*/exercise.json"))
            if not exercise_files:
                raise PackImportError(f"No exercises found in level: {level.id}")
            for exercise_file in exercise_files:
                self._validate_exercise(pack_root, exercise_file)
        return pack

    def _validate_exercise(self, pack_root: Path, exercise_file: Path) -> None:
        try:
            definition = self._exercise_loader.load(exercise_file)
        except ExerciseDefinitionError as error:
            relative = exercise_file.relative_to(pack_root)
            raise PackImportError(f"{relative}: {error}") from error

        exercise_dir = exercise_file.parent
        subject_path = exercise_dir / definition.subject
        if not subject_path.is_file():
            raise PackImportError(
                f"{subject_path.relative_to(pack_root)}: subject file not found."
            )
        if definition.execution.fixture is not None:
            fixture_path = exercise_dir / definition.execution.fixture
            if not fixture_path.is_file():
                raise PackImportError(
                    f"{fixture_path.relative_to(pack_root)}: fixture file not found."
                )
        if definition.execution.reference is not None:
            reference_path = exercise_dir / definition.execution.reference
            if not reference_path.is_file():
                raise PackImportError(
                    f"{reference_path.relative_to(pack_root)}: reference file not found."
                )
        for support_file in definition.support_files:
            support_path = exercise_dir / support_file
            if not support_path.is_file():
                raise PackImportError(
                    f"{support_path.relative_to(pack_root)}: support file not found."
                )

    @staticmethod
    def _prepare_source(source: Path, temp_dir: Path) -> Path:
        if source.is_dir():
            return source
        if zipfile.is_zipfile(source):
            extract_dir = temp_dir / "pack"
            with zipfile.ZipFile(source) as archive:
                archive.extractall(extract_dir)
            if (extract_dir / "pack.json").is_file():
                return extract_dir
            children = [child for child in extract_dir.iterdir()]
            if len(children) == 1 and children[0].is_dir():
                return children[0]
            pack_json_files = list(extract_dir.rglob("pack.json"))
            if len(pack_json_files) == 1:
                return pack_json_files[0].parent
            return extract_dir
        raise PackImportError(f"Unsupported pack source: {source}")
