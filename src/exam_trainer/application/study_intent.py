from __future__ import annotations

from dataclasses import dataclass

from exam_trainer.application.capabilities import ExerciseCapabilities
from exam_trainer.ports.runtime_port import RuntimeStatus


@dataclass(frozen=True)
class StudyIntent:
    topic: str
    level: str
    goal: str
    format: str
    programming_language: str
    content_language: str
    size: str


class PackPromptBuilder:
    """Turns a study intent into a vendor-neutral pack generation prompt."""

    def __init__(
        self,
        *,
        capabilities: ExerciseCapabilities,
        runtime_statuses: tuple[RuntimeStatus, ...],
        pack_contract: str,
    ) -> None:
        self._capabilities = capabilities
        self._runtime_statuses = runtime_statuses
        self._pack_contract = pack_contract

    def build(self, intent: StudyIntent) -> str:
        topic = intent.topic.strip() or "fundamentos de programação"
        runtime_lines = [self._runtime_line(status) for status in self._runtime_statuses]
        if not runtime_lines:
            runtime_lines = ["- Nenhum runtime registrado nesta instalação."]

        languages = ", ".join(sorted(self._capabilities.languages)) or "nenhuma"
        executions = ", ".join(sorted(self._capabilities.executions.supported)) or "nenhuma"
        generators = ", ".join(sorted(self._capabilities.generators.supported)) or "nenhum"
        expectations = ", ".join(sorted(self._capabilities.expectations.supported)) or "nenhuma"
        reference_required = ", ".join(sorted(self._capabilities.expectations.reference_required)) or "nenhuma"

        return "\n".join(
            (
                "Crie um pack para o Exam Trainer.",
                "",
                "Intencao de estudo:",
                f"- Topico: {topic}",
                f"- Nivel: {intent.level}",
                f"- Objetivo: {intent.goal}",
                f"- Formato: {intent.format}",
                f"- Linguagem de programacao: {intent.programming_language}",
                f"- Idioma dos subjects/conteudo: {intent.content_language}",
                f"- Tamanho: {intent.size}",
                "",
                "Use apenas as capabilities suportadas por esta versao do Exam Trainer.",
                "Nao invente campos fora do contrato. Nao inclua scripts arbitrarios.",
                "Gere subjects em Markdown, arquivos de atividade, validation plans, casos de teste e referencias apenas quando algum validator realmente exigir.",
                "Explique ao final como validar/importar o pack no Exam Trainer.",
                "",
                "Capabilities disponiveis:",
                f"- Linguagens do contrato: {languages}",
                f"- Execution strategies: {executions}",
                f"- Generators: {generators}",
                f"- Expectations/validators: {expectations}",
                f"- Expectations que exigem reference: {reference_required}",
                "",
                "Runtimes registrados nesta instalacao:",
                *runtime_lines,
                "",
                "Contrato atual do pack:",
                "```markdown",
                self._pack_contract.strip(),
                "```",
            )
        )

    @staticmethod
    def _runtime_line(status: RuntimeStatus) -> str:
        availability = "disponivel" if status.available else "indisponivel/nao verificado"
        tool = f" ({status.tool})" if status.tool else ""
        return f"- {status.display_name} [{status.language}]: {availability}{tool}"
