# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['src/exam_trainer/main.py'],
    pathex=['src'],
    binaries=[],
    # Só conteúdo público: packs de exemplo, README e o contrato de pack.
    # _local/ (material privado local e artefatos de agentes) NÃO entra no executável.
    datas=[
        ('examples', 'examples'),
        ('README.md', '.'),
        ('src/exam_trainer/resources/*.md', 'exam_trainer/resources'),
    ],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='Exam Trainer',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

