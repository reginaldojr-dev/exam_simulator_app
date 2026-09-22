"""Tokens visuais.

Este módulo é Python puro (sem PySide6): descreve *o que* um tema é.
O QSS e os componentes só leem estes nomes, nunca cores literais.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ThemeTokens:
    key: str
    name: str

    # superfícies
    background: str          # fundo da janela
    surface: str             # painéis de texto (subject, trace, tabela)
    surface_alt: str         # cards / faixas de destaque
    hover_background: str    # fundo em hover/foco
    selected_background: str # fundo de item selecionado (tab, opção marcada)
    pressed_background: str  # fundo pressionado

    # texto
    accent: str              # títulos, borda de foco, cursor, indicadores
    text_primary: str        # texto corrido
    text_bright: str         # texto em hover/selected
    text_secondary: str      # labels secundárias, dicas, IDs
    text_disabled: str

    # bordas
    border: str              # borda discreta (painéis, botões em repouso)
    border_strong: str       # borda de destaque (hover/foco/selected)
    bevel: str               # "degrau" inferior dos botões (visual de tecla)
    border_disabled: str

    # estados semânticos (nunca usados como acento)
    success: str             # PASS
    fail: str                # FAIL
    warning: str             # PENDENTE / em andamento / atenção
    fail_background: str     # hover de botão destrutivo / banner de FAIL
    success_background: str  # banner de PASS

    # tipografia e forma
    font_body: str = 'Consolas, "Cascadia Mono", "JetBrains Mono", "DejaVu Sans Mono", "Courier New", monospace'
    font_title: str = 'Consolas, "Cascadia Mono", "JetBrains Mono", "DejaVu Sans Mono", "Courier New", monospace'
    font_size: int = 13
    title_size: int = 28
    radius: int = 0
    bevel_width: int = 4

    # comportamento visual
    blink_cursor: bool = True       # cursor "_" piscando em título/foco
    cursor_char: str = "_"
    animations: bool = True         # fade de tela, typewriter, banner

    def get(self, token: str) -> str:
        value = getattr(self, token)
        if not isinstance(value, str):
            raise KeyError(token)
        return value
