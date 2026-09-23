from __future__ import annotations

from collections.abc import Iterable

from exam_trainer.ports.runtime_port import LanguageRuntime


class UnsupportedLanguageError(ValueError):
    pass


class RuntimeRegistry:
    """language -> runtime. Único lugar que sabe quais linguagens o app executa."""

    def __init__(self, runtimes: Iterable[LanguageRuntime] = ()) -> None:
        self._runtimes: dict[str, LanguageRuntime] = {}
        for runtime in runtimes:
            self.register(runtime)

    def register(self, runtime: LanguageRuntime) -> None:
        self._runtimes[runtime.language] = runtime

    def get(self, language: str) -> LanguageRuntime:
        try:
            return self._runtimes[language]
        except KeyError as error:
            raise UnsupportedLanguageError(f"Nenhum runtime instalado para a linguagem: {language}.") from error

    def has(self, language: str) -> bool:
        return language in self._runtimes

    def languages(self) -> tuple[str, ...]:
        return tuple(sorted(self._runtimes))
