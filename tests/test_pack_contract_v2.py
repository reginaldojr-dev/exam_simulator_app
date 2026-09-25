"""Passo 5a: contrato de pack v2 e normalização do v1."""

from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path, PurePosixPath

from exam_trainer.adapters.compiler.system_c_compiler import SystemCCompiler
from exam_trainer.adapters.exercise_definition.json_loader import (
    ExerciseDefinitionError,
    JsonExerciseDefinitionLoader,
)
from exam_trainer.adapters.grader.generic_c_grader import GenericCGrader
from exam_trainer.adapters.pack.json_pack_loader import JsonPackLoader, PackDefinitionError
from exam_trainer.adapters.pack.local_pack_catalog import LocalPackCatalog
from exam_trainer.adapters.pack.local_pack_importer import LocalPackImporter, PackImportError
from exam_trainer.domain.exercise_definition import ReferenceDefinition
from exam_trainer.domain.grading import GradingPolicy
from exam_trainer.ports.grader_port import GradingRequest

REPO = Path(__file__).resolve().parent.parent
SAMPLE = REPO / "examples" / "packs" / "sample_rank"
C_BASICS = REPO / "examples" / "packs" / "c-basics"


def v1_exercise(**overrides: object) -> dict[str, object]:
    data: dict[str, object] = {
        "id": "ex",
        "name": "Ex",
        "subject": "subject.md",
        "submission": {"filename": "ex.c"},
        "execution": {"type": "program_output"},
        "tests": {"generator": "random_arguments", "expectation": "echo_arguments"},
    }
    data.update(overrides)
    return data


def v2_exercise(**overrides: object) -> dict[str, object]:
    data: dict[str, object] = {
        "schema_version": 2,
        "id": "ex",
        "name": "Ex",
        "subject": "subject.md",
        "topics": ["strings", "loops"],
        "submission": {"filename": "ex.c"},
        "execution": {"type": "program_output"},
        "reference": {"source": "reference/ex.c"},
        "tests": {"generator": "random_arguments", "expectation": "reference_output"},
    }
    data.update(overrides)
    return data


def v3_exercise(**overrides: object) -> dict[str, object]:
    data: dict[str, object] = {
        "schema_version": 3,
        "id": "ex",
        "type": "exercise",
        "name": "Ex",
        "subject": "subject.md",
        "language": "c",
        "topics": ["strings", "loops"],
        "submission": {"filename": "ex.c"},
        "validation": {
            "strategy": "function_call",
            "harness": "harness/main.c",
            "reference": {"source": "solution/ex.c", "harness": "harness/main.c"},
            "tests": {"generator": "random_arguments", "expectation": "reference_output"},
            "limits": {"timeout_seconds": 2},
        },
    }
    data.update(overrides)
    return data


class ExerciseContractTest(unittest.TestCase):
    def load(self, data: dict[str, object], language: str = "c"):
        return JsonExerciseDefinitionLoader().load_data(data, language)

    # --------------------------------------------------------------- v1
    def test_v1_without_schema_version_stays_v1(self) -> None:
        definition = self.load(v1_exercise())
        self.assertEqual(definition.schema_version, 1)
        self.assertEqual(definition.language, "c")
        self.assertEqual(definition.topics, ())
        self.assertIsNone(definition.reference)

    def test_v1_function_with_main_is_an_alias_of_function_call(self) -> None:
        definition = self.load(v1_exercise(execution={"type": "function_with_main", "fixture": "fixtures/main.c"}))
        self.assertEqual(definition.execution.type, "function_call")
        self.assertEqual(definition.execution.declared_type, "function_with_main")
        self.assertEqual(definition.execution.harness, PurePosixPath("fixtures/main.c"))

    def test_v1_reference_compare_without_fixture_is_program_output_with_reference(self) -> None:
        definition = self.load(
            v1_exercise(
                execution={"type": "reference_compare", "reference": "fixtures/reference.c"},
                tests={"generator": "random_arguments", "expectation": "reference_output"},
            )
        )
        self.assertEqual(definition.execution.type, "program_output")
        self.assertEqual(definition.reference, ReferenceDefinition(source=PurePosixPath("fixtures/reference.c")))
        self.assertEqual(definition.executable_files, (PurePosixPath("fixtures/reference.c"),))

    def test_v1_ignores_unknown_fields_as_before(self) -> None:
        self.load(v1_exercise(author="someone"))

    # --------------------------------------------------------------- v2
    def test_loads_v2_with_topics_and_decoupled_reference(self) -> None:
        definition = self.load(
            v2_exercise(
                execution={"type": "function_call", "harness": "harness/main.c"},
                reference={"source": "reference/ex.c", "harness": "harness/main.c"},
            )
        )
        self.assertEqual(definition.schema_version, 2)
        self.assertEqual(definition.topics, ("strings", "loops"))
        self.assertEqual(definition.execution.type, "function_call")
        self.assertEqual(definition.reference.harness, PurePosixPath("harness/main.c"))
        self.assertEqual(
            definition.executable_files,
            (PurePosixPath("harness/main.c"), PurePosixPath("reference/ex.c")),
        )

    def test_loads_v3_activity_validation_plan(self) -> None:
        definition = self.load(v3_exercise())

        self.assertEqual(definition.schema_version, 3)
        self.assertEqual(definition.activity.identity.type, "exercise")
        self.assertEqual(definition.activity.language, "c")
        self.assertEqual(definition.execution.type, "function_call")
        self.assertEqual(definition.reference.source, PurePosixPath("solution/ex.c"))
        self.assertEqual(definition.validation_plan.primary.strategy, "function_call")

    def test_v2_and_normalized_v1_are_the_same_model(self) -> None:
        v1 = self.load(
            v1_exercise(
                execution={"type": "reference_compare", "fixture": "f/main.c", "reference": "f/ref.c"},
                tests={"generator": "random_arguments", "expectation": "reference_output"},
            )
        )
        v2 = self.load(
            v2_exercise(
                topics=[],
                execution={"type": "function_call", "harness": "f/main.c"},
                reference={"source": "f/ref.c", "harness": "f/main.c"},
            )
        )
        self.assertEqual(v1.execution.type, v2.execution.type)
        self.assertEqual(v1.execution.harness, v2.execution.harness)
        self.assertEqual(v1.reference, v2.reference)

    # ------------------------------------------------------------ rejeições
    def test_rejects_invalid_schema_version(self) -> None:
        for value in (0, "2", True, 2.0):
            with self.subTest(value=value), self.assertRaisesRegex(ExerciseDefinitionError, "schema_version"):
                self.load(v2_exercise(schema_version=value))

    def test_rejects_unsupported_capabilities(self) -> None:
        cases = {
            "custom execution": v1_exercise(execution={"type": "custom"}),
            "unknown generator": v1_exercise(tests={"generator": "fuzz", "expectation": "literal"}),
            "unknown expectation": v1_exercise(tests={"generator": "random_arguments", "expectation": "magic"}),
        }
        for name, data in cases.items():
            with self.subTest(name), self.assertRaises(ExerciseDefinitionError):
                self.load(data)
        with self.assertRaisesRegex(ExerciseDefinitionError, "Unsupported language"):
            self.load(v1_exercise(), language="rust")

    def test_v2_is_strict(self) -> None:
        with self.assertRaisesRegex(ExerciseDefinitionError, "Unknown field"):
            self.load(v2_exercise(author="x"))
        with self.assertRaisesRegex(ExerciseDefinitionError, "requires a reference"):
            data = v2_exercise()
            del data["reference"]
            self.load(data)
        with self.assertRaisesRegex(ExerciseDefinitionError, "harness is required"):
            self.load(v2_exercise(execution={"type": "function_call"}))
        with self.assertRaisesRegex(ExerciseDefinitionError, "not used for c"):
            self.load(v2_exercise(execution={"type": "program_output", "entry": "main"}))
        with self.assertRaisesRegex(ExerciseDefinitionError, "only valid with reference_compare"):
            self.load(v2_exercise(execution={"type": "program_output", "reference": "r.c"}))
        with self.assertRaisesRegex(ExerciseDefinitionError, "only once"):
            self.load(
                v2_exercise(execution={"type": "reference_compare", "reference": "r.c"}, reference={"source": "r.c"})
            )
        with self.assertRaisesRegex(ExerciseDefinitionError, "unsafe|relative|\\.\\."):
            self.load(v2_exercise(reference={"source": "../outside.c"}))

    def test_top_level_reference_requires_v2(self) -> None:
        with self.assertRaisesRegex(ExerciseDefinitionError, "schema_version 2"):
            self.load(v1_exercise(reference={"source": "r.c"}))


class PackContractTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def write_pack(self, pack: dict[str, object], exercise: dict[str, object] | None = None) -> Path:
        root = self.root / "src_pack"
        exercise_dir = root / "level0" / "ex"
        (exercise_dir / "reference").mkdir(parents=True)
        (exercise_dir / "subject.md").write_text("subject", encoding="utf-8")
        (exercise_dir / "reference" / "ex.c").write_text("int main(void){return 0;}", encoding="utf-8")
        (exercise_dir / "exercise.json").write_text(json.dumps(exercise or v2_exercise()), encoding="utf-8")
        (root / "pack.json").write_text(json.dumps(pack), encoding="utf-8")
        return root

    @staticmethod
    def v2_pack(**overrides: object) -> dict[str, object]:
        pack: dict[str, object] = {
            "schema_version": 2,
            "id": "v2pack",
            "name": "V2 Pack",
            "version": "2.0.0",
            "language": "c",
            "topics": ["basics"],
            "exam": {"duration_minutes": 60},
            "levels": [{"id": "level0", "path": "level0"}],
        }
        pack.update(overrides)
        return pack

    def test_repository_sample_pack_uses_v3_contract(self) -> None:
        pack = JsonPackLoader().load(SAMPLE / "pack.json")
        self.assertEqual((pack.schema_version, pack.language, pack.topics), (3, "c", ()))

    def test_loads_v2_pack(self) -> None:
        root = self.write_pack(self.v2_pack())
        pack = JsonPackLoader().load(root / "pack.json")
        self.assertEqual((pack.schema_version, pack.language, pack.topics), (2, "c", ("basics",)))

    def test_rejects_invalid_pack_schema_and_language(self) -> None:
        for overrides, message in (
            ({"schema_version": 9}, "schema_version"),
            ({"language": "cobol"}, "Unsupported language"),
            ({"owner": "me"}, "Unknown field"),
            ({"topics": "strings"}, "topics"),
        ):
            with self.subTest(overrides=overrides):
                root = self.write_pack(self.v2_pack(**overrides))
                with self.assertRaisesRegex(PackDefinitionError, message):
                    JsonPackLoader().load(root / "pack.json")
                shutil.rmtree(root)

    def test_importer_accepts_v2_and_reports_reference_as_executable(self) -> None:
        root = self.write_pack(self.v2_pack())
        report = LocalPackImporter(self.root / "managed").inspect_pack(root)
        self.assertEqual(report.pack.schema_version, 2)
        self.assertEqual(report.executable_files, ("level0/ex/reference/ex.c",))

    def test_importer_rejects_missing_v2_reference_file(self) -> None:
        root = self.write_pack(self.v2_pack(), v2_exercise(reference={"source": "reference/missing.c"}))
        with self.assertRaisesRegex(PackImportError, "not found"):
            LocalPackImporter(self.root / "managed").inspect_pack(root)

    def test_bundled_packs_use_v3_contract(self) -> None:
        for pack_root, expected in ((SAMPLE, None), (C_BASICS, 5)):
            with self.subTest(pack=pack_root.name):
                report = LocalPackImporter(self.root / "managed").inspect_pack(pack_root)
                self.assertEqual(report.pack.schema_version, 3)
                if expected is not None:
                    self.assertEqual(report.exercise_count, expected)


@unittest.skipUnless(SystemCCompiler().is_available(), "no compatible C compiler")
class CBasicsPackGradingRegressionTest(unittest.TestCase):
    """Não-regressão do caminho C: submissões válidas passam sem depender de solution."""

    def test_valid_submissions_pass_and_empty_submission_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            shutil.copytree(C_BASICS, root / "bundled" / C_BASICS.name)
            catalog = LocalPackCatalog(root / "managed", bundled_packs_dir=root / "bundled")
            grader = GenericCGrader(SystemCCompiler())
            refs = catalog.list_exercises("c-basics")
            self.assertEqual(len(refs), 5)
            submissions = {
                "argc_counter": "#include <stdio.h>\nint main(int argc,char**argv){(void)argv; printf(\"%d\\n\", argc - 1); return 0;}\n",
                "char_stats": "#include <stdio.h>\nint main(int argc,char**argv){int lo=0,up=0,d=0,o=0; if(argc>1){for(char*p=argv[1];*p;p++){if(*p>='a'&&*p<='z')lo++;else if(*p>='A'&&*p<='Z')up++;else if(*p>='0'&&*p<='9')d++;else o++;}} printf(\"%d %d %d %d\\n\",lo,up,d,o); return 0;}\n",
                "ft_strlen_lite": "#include <stddef.h>\nsize_t ft_strlen_lite(const char *s){size_t n=0; while(s[n]) n++; return n;}\n",
                "array_peak": "#include <stdio.h>\n#include <stdlib.h>\nint main(int argc,char**argv){if(argc<2){printf(\"0\\n\"); return 0;} int best=atoi(argv[1]); for(int i=2;i<argc;i++){int v=atoi(argv[i]); if(v>best) best=v;} printf(\"%d\\n\", best); return 0;}\n",
                "parse_sum": "#include <stdio.h>\nint parse(char*s,int*ok){int sign=1,i=0,n=0;*ok=0;if(s[0]=='-'){sign=-1;i++;}else if(s[0]=='+')i++; if(!s[i])return 0; for(;s[i];i++){if(s[i]<'0'||s[i]>'9')return 0; n=n*10+s[i]-'0';}*ok=1;return sign*n;} int main(int argc,char**argv){int total=0,ok; for(int i=1;i<argc;i++){int v=parse(argv[i],&ok); if(ok) total+=v;} printf(\"%d\\n\", total); return 0;}\n",
            }
            failures = []
            for index, ref in enumerate(refs):
                definition = ref.definition
                workspace = root / "ws" / definition.id
                workspace.mkdir(parents=True)
                (workspace / definition.submission.filename).write_text(submissions[definition.id], encoding="utf-8")
                result = grader.grade(
                    GradingRequest(
                        definition=definition,
                        exercise_path=ref.content_path,
                        workspace_path=workspace,
                        policy=GradingPolicy.exam(),
                        seed=1000 + index,
                    )
                )
                if not result.passed:
                    failures.append(definition.id)
            self.assertEqual(failures, [])

            first = refs[0]
            empty = root / "ws_empty"
            empty.mkdir()
            (empty / first.definition.submission.filename).write_text("", encoding="utf-8")
            result = grader.grade(
                GradingRequest(
                    definition=first.definition,
                    exercise_path=first.content_path,
                    workspace_path=empty,
                    policy=GradingPolicy.exam(),
                    seed=1,
                )
            )
            self.assertFalse(result.passed)


if __name__ == "__main__":
    unittest.main()
