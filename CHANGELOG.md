# Changelog

## 1.0.0 - V1

- Core: hexagonal boundaries for domain/application/ports/adapters, session policies for Training and Exam, activity identity, progress, history and workspace scopes.
- Runtimes: generic `RuntimeRegistry` with C, C++, Python and Java/JDK support, availability checks and missing-toolchain preflight.
- Packs: contract v3 with `programming_language`, `content_language`, Markdown subjects, usage constraints, validation plans and optional references only when a validator requires them.
- UI: PySide6 desktop app with Home, Training, Exam, History, Settings, Markdown subject rendering and StudyIntent prompt generation for pack creation.
- Persistence: local SQLite schema v3 with migrations and backups for existing databases.
- Build: PyInstaller flow for `Exam Trainer.exe`, safe staging replacement, build cache, Windows App Control messaging and SHA-256 checksum generation.

Known external pending item: trusted code signing for public Windows releases.
