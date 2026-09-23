from __future__ import annotations

import shutil
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path

from exam_trainer.adapters.exercise_definition.json_loader import (
    ExerciseDefinitionError,
    JsonExerciseDefinitionLoader,
)
from exam_trainer.adapters.pack.json_pack_loader import JsonPackLoader, PackDefinitionError
from exam_trainer.adapters.pack.pack_security import (
    PackSecurityError,
    ensure_inside,
    reject_links,
    safe_join,
    validate_zip,
)
from exam_trainer.domain.pack_definition import PackDefinition


class PackImportError(ValueError):
    pass


@dataclass(frozen=True)
class PackImportReport:
    """Resultado da validação de um pack, antes de copiá-lo.

    `executable_files`: arquivos do pack que serão COMPILADOS/EXECUTADOS durante a
    correção (fixtures e references). A importação em si nunca executa nada.
    """

    pack: PackDefinition
    exercise_count: int
    executable_files: tuple[str, ...]

    @property
    def has_executable_code(self) -> bool:
        return bool(self.executable_files)


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

    def inspect_pack(self, source_path: Path | str) -> PackImportReport:
        """Valida o pack (pasta ou ZIP) sem copiar nada."""
        source = Path(source_path)
        if not source.exists():
            raise PackImportError(f"Pack source does not exist: {source}")
        with tempfile.TemporaryDirectory() as temp_dir:
            prepared_source = self._prepare_source(source, Path(temp_dir))
            return self.validate_pack(prepared_source)

    def import_pack(self, source_path: Path | str) -> PackDefinition:
        source = Path(source_path)
        if not source.exists():
            raise PackImportError(f"Pack source does not exist: {source}")

        with tempfile.TemporaryDirectory() as temp_dir:
            prepared_source = self._prepare_source(source, Path(temp_dir))
            report = self.validate_pack(prepared_source)
            pack = report.pack
            self._managed_packs_dir.mkdir(parents=True, exist_ok=True)
            try:
                destination = ensure_inside(self._managed_packs_dir, self._managed_packs_dir / pack.id)
            except PackSecurityError as error:
                raise PackImportError(str(error)) from error
            if destination.exists():
                shutil.rmtree(destination)
            # A árvore já foi verificada sem links; symlinks=True impede seguir qualquer
            # link que apareça entre a validação e a cópia.
            shutil.copytree(prepared_source, destination, symlinks=True)
            return pack

    def validate_pack(self, pack_root: Path) -> PackImportReport:
        pack_root = pack_root.resolve()
        try:
            reject_links(pack_root)
            pack = self._pack_loader.load(safe_join(pack_root, "pack.json"))
        except (PackDefinitionError, PackSecurityError) as error:
            raise PackImportError(str(error)) from error

        executable: list[str] = []
        exercise_count = 0
        seen_ids: set[str] = set()
        for level in pack.levels:
            try:
                level_path = safe_join(pack_root, level.path)
            except PackSecurityError as error:
                raise PackImportError(f"level {level.id}: {error}") from error
            if not level_path.is_dir():
                raise PackImportError(f"Level path not found: {level.path}")
            exercise_files = sorted(level_path.glob("*/exercise.json"))
            if not exercise_files:
                raise PackImportError(f"No exercises found in level: {level.id}")
            for exercise_file in exercise_files:
                exercise_id, files = self._validate_exercise(pack_root, exercise_file)
                if exercise_id in seen_ids:
                    raise PackImportError(f"Duplicated exercise id in pack: {exercise_id}")
                seen_ids.add(exercise_id)
                executable.extend(files)
                exercise_count += 1
        return PackImportReport(
            pack=pack,
            exercise_count=exercise_count,
            executable_files=tuple(executable),
        )

    def _validate_exercise(self, pack_root: Path, exercise_file: Path) -> tuple[str, list[str]]:
        relative = exercise_file.relative_to(pack_root)
        try:
            definition = self._exercise_loader.load(exercise_file)
        except ExerciseDefinitionError as error:
            raise PackImportError(f"{relative}: {error}") from error

        exercise_dir = exercise_file.parent
        executable: list[str] = []

        def check(declared, label: str, runnable: bool = False) -> None:
            try:
                path = safe_join(exercise_dir, declared)
            except PackSecurityError as error:
                raise PackImportError(f"{relative}: {label}: {error}") from error
            if not path.is_file():
                raise PackImportError(
                    f"{path.relative_to(pack_root)}: {label} file not found."
                )
            if runnable:
                executable.append(path.relative_to(pack_root).as_posix())

        check(definition.subject, "subject")
        if definition.execution.fixture is not None:
            check(definition.execution.fixture, "fixture", runnable=True)
        if definition.execution.reference is not None:
            check(definition.execution.reference, "reference", runnable=True)
        for support_file in definition.support_files:
            check(support_file, "support")
        return definition.id, executable

    @staticmethod
    def _prepare_source(source: Path, temp_dir: Path) -> Path:
        if source.is_dir():
            return source
        if zipfile.is_zipfile(source):
            extract_dir = temp_dir / "pack"
            with zipfile.ZipFile(source) as archive:
                try:
                    validate_zip(archive)
                except PackSecurityError as error:
                    raise PackImportError(str(error)) from error
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
