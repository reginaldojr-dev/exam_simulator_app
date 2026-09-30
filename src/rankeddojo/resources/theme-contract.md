# Theme Contract — RankedDojo

Single source of truth for the declarative `theme.json` contract supported by this
version of the app.

External themes are purely declarative: they describe visual tokens and metadata
only. They cannot declare Python, shell commands, callbacks, scripts, imports,
graders, or any embedded plugin. Loading a `theme.json` never executes anything
from it -- the loader only reads JSON, validates every field against an explicit
whitelist, and builds an internal `ThemeTokens` value. Any field outside that
whitelist is rejected, including anything named like code (`script`, `command`,
`entrypoint`, `plugin`, ...).

## Folder structure

Each user theme lives in its own subfolder under the app's themes folder, inside
the app's persistent config directory (same root as `config.json`):

```text
<app config dir>/themes/
├── my-theme/
│   └── theme.json
└── another-theme/
    └── theme.json
```

On Windows this is `%APPDATA%\rankeddojo\themes\`; on macOS
`~/Library/Application Support/rankeddojo/themes/`; on Linux
`$XDG_CONFIG_HOME/rankeddojo/themes/` (or `~/.config/rankeddojo/themes/`). The
folder name itself is not meaningful -- it only needs to contain a `theme.json`. A
subfolder with no `theme.json` inside is silently ignored.

## Minimal `theme.json`

```json
{
  "schema_version": 1,
  "id": "my-theme",
  "name": "My Theme",
  "tokens": {
    "accent": "#34e0a1",
    "accent_secondary": "#8b5cf6"
  }
}
```

A theme only needs to declare `schema_version`, `id`, `name`, and `tokens` -- and
`tokens` itself may declare as few or as many fields as it wants (see
"Partial tokens and inheritance" below).

## Top-level fields

| Field            | Required | Notes                                                             |
| ---------------- | -------- | ------------------------------------------------------------------ |
| `schema_version` | yes      | Currently only `1` is supported.                                   |
| `id`             | yes      | Stable, technical identifier. `[A-Za-z0-9][A-Za-z0-9_-]{0,63}`, no dots/spaces/path separators, not a reserved Windows name. This is the internal key; it never changes based on `name`. |
| `name`           | yes      | Presentation only. Any non-empty string up to 80 characters. Never drives logic. |
| `author`         | no       | Free-text, presentation only.                                      |
| `version`        | no       | Free-text, presentation only.                                      |
| `tokens`         | yes      | An object; see below.                                              |

No other top-level field is accepted. An unknown field (including `script`,
`command`, `entrypoint`, `plugin`) makes the whole file invalid.

## Accepted tokens

`tokens` mirrors the app's internal `ThemeTokens` contract. Every field below is
optional; anything not declared is inherited from the base theme (see next
section).

Colors (each must be a 6-digit hex string, e.g. `"#39ff14"`):

`background`, `surface`, `surface_alt`, `hover_background`, `selected_background`,
`pressed_background`, `accent`, `accent_secondary`, `text_primary`, `text_bright`,
`text_secondary`, `text_disabled`, `border`, `border_strong`, `bevel`,
`border_disabled`, `success`, `fail`, `warning`, `fail_background`,
`success_background`.

Fonts (non-empty CSS-style font-family strings, up to 200 characters):

`font_body`, `font_title`, `font_mono`. `font_mono` is the dedicated font for
technical content (traces, commands, terminal-style panels) -- it does not need
to match `font_body`.

Numbers (integers within the stated range):

`font_size` (6-96), `title_size` (6-128), `radius` (0-64), `bevel_width` (0-32).

Booleans:

`blink_cursor`, `animations`.

Misc:

`cursor_char` -- a short, non-empty string (up to 8 characters).

Any `tokens` field outside this list is rejected. An invalid value for an
accepted field (a malformed color, a non-string font, an out-of-range or
non-integer number, a non-boolean) also invalidates the whole theme.

## Partial tokens and inheritance

A theme may declare only a subset of the tokens above. Any token it does not
declare is filled in from one fixed, stable internal base theme (the app's
built-in default/fallback theme). This keeps external themes working as new
tokens are added to the app over time, and keeps a minimal `theme.json` short.

Inheritance is a single, flat step: an external theme only ever inherits from
that one fixed internal base. There is no `extends` chain between external
themes, and no recursive resolution -- keeping this simple is intentional.

## Duplicate ids

An external theme's `id` must not collide with an already-registered theme --
whether a built-in theme or another external theme loaded earlier. A colliding
theme is rejected outright: it never silently overrides the existing one. When
two external themes declare the same `id`, folders are visited in a
deterministic (sorted) order, so the first one found is the one that is kept;
the later one is rejected the same way as a collision with a built-in theme.

## Invalid themes

A `theme.json` that fails validation for any reason (invalid JSON, unsupported
`schema_version`, invalid `id`, missing `name`, non-object `tokens`, an unknown
or invalid token, a duplicate `id`, ...) is skipped. It is reported in a
controlled, diagnosable way (never a crash, never a silently swallowed
exception) and never prevents the rest of the app -- or any other valid theme --
from loading normally.

## Not covered by this contract

This version of the contract is tokens and metadata only. It does not support
external assets (custom SVG/PNG images, packaged fonts, external icons); those
may be added in a future contract version if there is a real need for them.
