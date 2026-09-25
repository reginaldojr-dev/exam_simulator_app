from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from exam_trainer.adapters.grader.generic_grader import GenericGrader
from exam_trainer.adapters.pack.local_pack_importer import LocalPackImporter
from exam_trainer.adapters.runtime.python_runtime import PythonRuntime
from exam_trainer.application.engine.runtime_registry import RuntimeRegistry
from exam_trainer.domain.grading import GradingPolicy
from exam_trainer.ports.grader_port import GradingRequest

REPO = Path(__file__).resolve().parent.parent
C_BASICS = REPO / "examples" / "packs" / "c-basics"
PYTHON_BASICS = REPO / "examples" / "packs" / "python-basics"
SYSTEM_PYTHON = PythonRuntime().check_available()


class ContentLanguageContractTest(unittest.TestCase):
    def test_python_pack_declares_programming_language_and_pt_br_content(self) -> None:
        report = LocalPackImporter(Path(self._tmpdir())).inspect_pack(PYTHON_BASICS)
        refs = self._refs(PYTHON_BASICS, "python-basics")

        self.assertEqual(report.pack.content_language, "pt-BR")
        self.assertEqual(refs["reverse_text"].definition.programming_language, "python")
        self.assertEqual(refs["reverse_text"].definition.content_language, "pt-BR")

    def test_c_pack_declares_programming_language_and_pt_br_content(self) -> None:
        report = LocalPackImporter(Path(self._tmpdir())).inspect_pack(C_BASICS)
        refs = self._refs(C_BASICS, "c-basics")

        self.assertEqual(report.pack.content_language, "pt-BR")
        self.assertEqual(refs["argc_counter"].definition.programming_language, "c")
        self.assertEqual(refs["argc_counter"].definition.content_language, "pt-BR")

    def test_subject_utf8_accents_are_loaded_without_affecting_language_runtime(self) -> None:
        refs = self._refs(C_BASICS, "c-basics")
        ref = refs["argc_counter"]
        subject = (ref.content_path / ref.definition.subject).read_text(encoding="utf-8")

        self.assertIn("quantos argumentos", subject)
        self.assertIn("## Permitido", subject)
        self.assertEqual(ref.definition.programming_language, "c")
        self.assertIn("write", ref.definition.usage.allowed.functions)
        self.assertIn("printf", ref.definition.usage.forbidden.functions)

    @unittest.skipUnless(SYSTEM_PYTHON, "no system Python")
    def test_grading_does_not_depend_on_content_language(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            shutil.copytree(PYTHON_BASICS, root / "bundled" / "python-basics")
            refs = self._refs(root / "bundled" / "python-basics", "python-basics")
            ref = refs["count_args"]
            workspace = root / "workspace"
            workspace.mkdir()
            (workspace / ref.definition.submission.filename).write_text(
                "import sys\nprint(len(sys.argv) - 1)\n",
                encoding="utf-8",
            )
            definition = ref.definition
            self.assertEqual(definition.content_language, "pt-BR")

            result = GenericGrader(RuntimeRegistry([PythonRuntime()])).grade(
                GradingRequest(
                    definition=definition,
                    exercise_path=ref.content_path,
                    workspace_path=workspace,
                    policy=GradingPolicy.training(),
                    seed=1,
                )
            )

            self.assertTrue(result.passed, result.trace_data.as_text())

    def test_schema_uses_programming_language_not_content_language_for_runtime(self) -> None:
        exercise_json = PYTHON_BASICS / "level1" / "reverse_text" / "exercise.json"
        data = json.loads(exercise_json.read_text(encoding="utf-8"))

        self.assertEqual(data["programming_language"], "python")
        self.assertEqual(data["content_language"], "pt-BR")
        self.assertNotIn("language", data)

    @staticmethod
    def _refs(pack_root: Path, pack_id: str):
        from exam_trainer.adapters.pack.local_pack_catalog import LocalPackCatalog

        catalog = LocalPackCatalog(Path("does-not-exist"), bundled_packs_dir=pack_root.parent)
        return {ref.definition.id: ref for ref in catalog.list_exercises(pack_id)}

    @staticmethod
    def _tmpdir() -> str:
        temp = tempfile.TemporaryDirectory()
        path = temp.name
        temp.cleanup()
        return path


if __name__ == "__main__":
    unittest.main()
