"""Content providers for the learning track model (Fase 9).

Nothing here executes a grader, opens a workspace, touches PySide6, or
reaches the network -- a provider only reads content that some other,
already-existing system (`LocalPackCatalog` today) has discovered and
validated, and re-shapes the parts that opted in
(`PackDefinition.learning_track`) into `LearningActivityRef` values. See
`resources/learning-content-model.md`.
"""
