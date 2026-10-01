"""Local plugin support: Plugin API v1.

A plugin is trusted, opt-in, executable Python code -- distinct from a pack
(declarative content, never executable) and from an external theme
(declarative `theme.json`, whitelist-validated, never executable). See
`resources/plugin-api-v1.md` for the full contract.

RankedDojo works completely without any plugin installed or enabled; nothing
here is imported by `packs/` or `adapters/theme/`, and nothing in those two
imports this package.
"""
