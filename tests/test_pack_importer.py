from __future__ import annotations

import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from exam_trainer.adapters.pack.local_pack_importer import LocalPackImporter, PackImportError


def create_minimal_pack(root: Path) -> None:
    (root / "level0" / "echo_args").mkdir(parents=True)
    (root / "pack.json").write_text(
        json.dumps(
            {
                "id": "sample_rank",
                "name": "Sample Rank",
                "version": "1.0.0",
                "levels": [{"id": "level0", "path": "level0"}],
            }
        ),
        encoding="utf-8",
    )
    (root / "level0" / "echo_args" / "exercise.json").write_text(
        json.dumps(
            {
                "id": "echo_args",
                "name": "Echo Args",
                "subject": "subject.md",
                "submission": {"filename": "echo_args.c"},
                "execution": {"type": "program_output"},
                "tests": {
                    "generator": "random_arguments",
                    "expectation": "echo_arguments",
                },
            }
        ),
        encoding="utf-8",
    )
    (root / "level0" / "echo_args" / "subject.md").write_text(
        "# Echo Args\n",
        encoding="utf-8",
    )


class PackImporterTest(unittest.TestCase):
    def test_imports_valid_pack_to_managed_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "source"
            managed = root / "managed"
            source.mkdir()
            create_minimal_pack(source)

            pack = LocalPackImporter(managed).import_pack(source)

            self.assertEqual(pack.id, "sample_rank")
            self.assertTrue((managed / "sample_rank" / "pack.json").is_file())
            self.assertTrue(
                (
                    managed
                    / "sample_rank"
                    / "level0"
                    / "echo_args"
                    / "exercise.json"
                ).is_file()
            )

    def test_rejects_pack_when_subject_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "source"
            managed = root / "managed"
            source.mkdir()
            create_minimal_pack(source)
            (source / "level0" / "echo_args" / "subject.md").unlink()

            with self.assertRaisesRegex(PackImportError, "subject file not found"):
                LocalPackImporter(managed).import_pack(source)

            self.assertFalse(managed.exists())

    def test_repository_sample_pack_is_valid(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            managed = Path(temp_dir) / "managed"
            sample_pack = (
                Path(__file__).parent.parent
                / "examples"
                / "packs"
                / "sample_rank"
            )

            pack = LocalPackImporter(managed).import_pack(sample_pack)

            self.assertEqual(pack.id, "sample_rank")
            self.assertTrue((managed / "sample_rank" / "level0").is_dir())
            self.assertTrue((managed / "sample_rank" / "level1").is_dir())

    def test_repository_rank02_packs_are_valid(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            managed = Path(temp_dir) / "managed"
            packs_root = Path(__file__).parent.parent / "packs"
            importer = LocalPackImporter(managed)

            original = importer.import_pack(packs_root / "rank02-original")
            practice = importer.import_pack(packs_root / "rank02-practice")

            self.assertEqual(original.id, "rank02-original")
            self.assertEqual(practice.id, "rank02-practice")
            self.assertTrue((managed / "rank02-original" / "level3").is_dir())
            self.assertTrue((managed / "rank02-practice" / "level3").is_dir())

    def test_repository_rank02_exercise_ids_are_unique(self) -> None:
        packs_root = Path(__file__).parent.parent / "packs"
        for pack_root in (packs_root / "rank02-original", packs_root / "rank02-practice"):
            ids: set[str] = set()
            for exercise_json in pack_root.glob("level*/*/exercise.json"):
                data = json.loads(exercise_json.read_text(encoding="utf-8"))
                exercise_id = str(data["id"])
                self.assertNotIn(exercise_id, ids, msg=str(exercise_json))
                ids.add(exercise_id)
            self.assertEqual(len(ids), 55, msg=str(pack_root))

    def test_imports_pack_from_zip(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "source"
            managed = root / "managed"
            source.mkdir()
            create_minimal_pack(source)
            zip_path = root / "sample_rank.zip"
            with zipfile.ZipFile(zip_path, "w") as archive:
                for path in source.rglob("*"):
                    archive.write(path, path.relative_to(source))

            pack = LocalPackImporter(managed).import_pack(zip_path)

            self.assertEqual(pack.id, "sample_rank")
            self.assertTrue((managed / "sample_rank" / "pack.json").is_file())

    def test_imports_pack_from_zip_with_wrapper_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "source"
            managed = root / "managed"
            source.mkdir()
            create_minimal_pack(source)
            zip_path = root / "wrapped.zip"
            with zipfile.ZipFile(zip_path, "w") as archive:
                for path in source.rglob("*"):
                    archive.write(path, Path("wrapper") / path.relative_to(source))

            pack = LocalPackImporter(managed).import_pack(zip_path)

            self.assertEqual(pack.id, "sample_rank")
            self.assertTrue((managed / "sample_rank" / "pack.json").is_file())
