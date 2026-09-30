"""Available themes.

Rule for every theme: the `accent` color is never used as a large-area
background (button, row, tab, selected item). It appears in text, border,
cursor, and small details. Tests verify this.

To create a new theme: add ThemeTokens here and register it in THEMES. No screen
needs to change.
"""

from __future__ import annotations

from exam_trainer.adapters.ui.qt.theme.tokens import ThemeTokens

TERMINAL = ThemeTokens(
    key="terminal",
    name="Terminal (verde)",
    background="#0a0e0a",
    surface="#030503",
    surface_alt="#0d140d",
    hover_background="#102010",
    selected_background="#143614",
    pressed_background="#0b170b",
    accent="#39ff14",
    accent_secondary="#39ff14",
    text_primary="#8ff58a",
    text_bright="#d2ffcc",
    text_secondary="#4a6b4a",
    text_disabled="#2e452e",
    border="#2a5a2a",
    border_strong="#39ff14",
    bevel="#1b3d1b",
    border_disabled="#1a2e1a",
    success="#50fa7b",
    fail="#ff5555",
    warning="#f1fa8c",
    fail_background="#2a0d0d",
    success_background="#0f2a14",
)

AMBER = ThemeTokens(
    key="amber",
    name="Âmbar CRT",
    background="#110c06",
    surface="#070503",
    surface_alt="#1a1209",
    hover_background="#2a1c0a",
    selected_background="#3a2708",
    pressed_background="#1f1507",
    accent="#ffb000",
    accent_secondary="#ffb000",
    text_primary="#f0c47e",
    text_bright="#fff0d4",
    text_secondary="#8a6a44",
    text_disabled="#4d3b25",
    border="#5c4218",
    border_strong="#ffb000",
    bevel="#3d2b0f",
    border_disabled="#2e2211",
    success="#a8d672",
    fail="#ff6b5a",
    warning="#ffe08a",
    fail_background="#2e0f0b",
    success_background="#1d2a10",
)

GAMEBOY = ThemeTokens(
    key="gameboy",
    name="Game Boy",
    background="#0f380f",
    surface="#0a2a0a",
    surface_alt="#174417",
    hover_background="#1f4f1f",
    selected_background="#306230",
    pressed_background="#123d12",
    accent="#c4e538",
    accent_secondary="#c4e538",
    text_primary="#9bbc0f",
    text_bright="#e0f59a",
    text_secondary="#6f8f2a",
    text_disabled="#3f5f20",
    border="#306230",
    border_strong="#c4e538",
    bevel="#081f08",
    border_disabled="#1f451f",
    success="#c4e538",
    fail="#ff8a65",
    warning="#e9f59b",
    fail_background="#3d1f12",
    success_background="#1f4f1f",
)

NEON = ThemeTokens(
    key="neon",
    name="Neon Arcade",
    background="#0e0b16",
    surface="#07050c",
    surface_alt="#151024",
    hover_background="#221a3a",
    selected_background="#34205a",
    pressed_background="#1a1430",
    accent="#ff4fd8",
    accent_secondary="#4fd8ff",
    text_primary="#d9d2ff",
    text_bright="#ffffff",
    text_secondary="#7d72a8",
    text_disabled="#3f3760",
    border="#3a2d5e",
    border_strong="#ff4fd8",
    bevel="#241a40",
    border_disabled="#221a38",
    success="#3ee6c1",
    fail="#ff5c7a",
    warning="#ffd166",
    fail_background="#2e0c18",
    success_background="#0d2a26",
)

MINIMAL = ThemeTokens(
    key="minimal",
    name="Minimal (escuro)",
    background="#121417",
    surface="#0c0e10",
    surface_alt="#181b1f",
    hover_background="#1d2126",
    selected_background="#23324a",
    pressed_background="#191c20",
    accent="#7aa2f7",
    accent_secondary="#bb9af7",
    text_primary="#d4d8de",
    text_bright="#ffffff",
    text_secondary="#7c8490",
    text_disabled="#4a5058",
    border="#2c3138",
    border_strong="#7aa2f7",
    bevel="#2c3138",
    border_disabled="#23272c",
    success="#73d99f",
    fail="#f7768e",
    warning="#e0af68",
    fail_background="#2a1519",
    success_background="#15261d",
    font_body='"Segoe UI", "Inter", "Helvetica Neue", Arial, sans-serif',
    font_title='"Segoe UI", "Inter", "Helvetica Neue", Arial, sans-serif',
    title_size=24,
    radius=6,
    bevel_width=1,
    blink_cursor=False,
)

PAPER = ThemeTokens(
    key="paper",
    name="Papel (claro)",
    background="#ecebe4",
    surface="#f8f7f2",
    surface_alt="#e3e1d6",
    hover_background="#dcdacd",
    selected_background="#cfe0c9",
    pressed_background="#d2d0c2",
    accent="#2f6b2f",
    accent_secondary="#3a5f7d",
    text_primary="#23271f",
    text_bright="#0f140c",
    text_secondary="#6b6e63",
    text_disabled="#a3a597",
    border="#b3b0a2",
    border_strong="#2f6b2f",
    bevel="#9c998b",
    border_disabled="#cfcdc0",
    success="#2f7d32",
    fail="#b3261e",
    warning="#8a5d00",
    fail_background="#f3dcd8",
    success_background="#d8ecd4",
)

_SANS_UI_FONT = '"Segoe UI", "Inter", "Helvetica Neue", Arial, sans-serif'
_RETRO_MONO_FONT = 'Consolas, "Cascadia Mono", "JetBrains Mono", "DejaVu Sans Mono", monospace'

RANKEDDOJO_DEFAULT = ThemeTokens(
    key="default",
    name="RankedDojo (padrão)",
    background="#0d0f12",
    surface="#0a0c0f",
    surface_alt="#14171b",
    hover_background="#20252b",
    selected_background="#1f2e2b",
    pressed_background="#191c20",
    accent="#34e0a1",
    accent_secondary="#8b5cf6",
    text_primary="#cdd3da",
    text_bright="#ffffff",
    text_secondary="#7c8793",
    text_disabled="#4a5058",
    border="#262b31",
    border_strong="#34e0a1",
    bevel="#1a1e23",
    border_disabled="#23272c",
    success="#4ade80",
    fail="#f75f5f",
    warning="#f5c451",
    fail_background="#2a1519",
    success_background="#15261d",
    font_body=_SANS_UI_FONT,
    font_title=_SANS_UI_FONT,
    title_size=24,
    radius=10,
    bevel_width=1,
    blink_cursor=False,
)

RANKEDDOJO_GAMIFIED = ThemeTokens(
    key="gamified",
    name="RankedDojo (gamificado)",
    background="#0b0710",
    surface="#0e0912",
    surface_alt="#120c1c",
    hover_background="#2a1c45",
    selected_background="#341f52",
    pressed_background="#1a1430",
    accent="#b833ff",
    accent_secondary="#2be0a0",
    text_primary="#ded4f5",
    text_bright="#ffffff",
    text_secondary="#9282b8",
    text_disabled="#4a3d66",
    border="#3a2a5c",
    border_strong="#b833ff",
    bevel="#241a40",
    border_disabled="#2a1f45",
    success="#3ee6c1",
    fail="#ff4d6a",
    warning="#ffcb47",
    fail_background="#33101b",
    success_background="#0f2e26",
    font_body=_SANS_UI_FONT,
    font_title=_SANS_UI_FONT,
    title_size=26,
    radius=10,
    bevel_width=2,
    blink_cursor=False,
)

RANKEDDOJO_RETRO = ThemeTokens(
    key="retro",
    name="RankedDojo (retrô)",
    background="#0a0e0a",
    surface="#030503",
    surface_alt="#0d140d",
    hover_background="#102010",
    selected_background="#143614",
    pressed_background="#0b170b",
    accent="#39ff14",
    # Terminal/CRT concept: a single phosphor hue reads better than a second
    # distinct accent, so accent_secondary simply repeats accent here.
    accent_secondary="#39ff14",
    text_primary="#8ff58a",
    text_bright="#d2ffcc",
    text_secondary="#4a6b4a",
    text_disabled="#2e452e",
    border="#2a5a2a",
    border_strong="#39ff14",
    bevel="#1b3d1b",
    border_disabled="#1a2e1a",
    success="#50fa7b",
    fail="#ff5555",
    warning="#f1fa8c",
    fail_background="#2a0d0d",
    success_background="#0f2a14",
    # The whole UI leans on the same mono face here, body/title/technical
    # content alike -- the terminal concept calls for it naturally, per-theme,
    # with no special-casing anywhere else in the codebase.
    font_body=_RETRO_MONO_FONT,
    font_title=_RETRO_MONO_FONT,
    font_mono=_RETRO_MONO_FONT,
    title_size=24,
    radius=0,
    bevel_width=2,
    blink_cursor=True,
)

THEMES: dict[str, ThemeTokens] = {
    theme.key: theme
    for theme in (
        TERMINAL,
        MINIMAL,
        AMBER,
        GAMEBOY,
        NEON,
        PAPER,
        RANKEDDOJO_DEFAULT,
        RANKEDDOJO_GAMIFIED,
        RANKEDDOJO_RETRO,
    )
}
# Kept as "terminal" for backward compatibility: existing persisted configs
# store this key, and get_theme() falls back to it for unknown/missing keys.
# Making one of the new RankedDojo themes the default is a product decision
# for a later phase, not an automatic consequence of adding them here.
DEFAULT_THEME_KEY = TERMINAL.key


def get_theme(key: str | None) -> ThemeTokens:
    return THEMES.get(key or DEFAULT_THEME_KEY, THEMES[DEFAULT_THEME_KEY])
