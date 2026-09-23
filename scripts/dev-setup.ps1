# Prepara o ambiente de desenvolvimento do 42 Exam Trainer (Windows / PowerShell).
#
#   powershell -ExecutionPolicy Bypass -File .\scripts\dev-setup.ps1
#   powershell -ExecutionPolicy Bypass -File .\scripts\dev-setup.ps1 -RunTests
#
# O que faz:
#   1. cria .venv na raiz do projeto (se nao existir);
#   2. instala o projeto em modo editavel com o extra [build] (PyInstaller);
#   3. confirma que `exam_trainer` e importado de src/ DESTE checkout;
#   4. avisa (sem alterar nada) se o Python global tem outra copia instalada.
# Nunca desinstala nada do Python global: isso fica a cargo de quem roda o script.
param([switch]$RunTests)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root
$Dist = "42-exam-trainer"   # [project].name em pyproject.toml

if (-not (Test-Path "$Root\.venv\Scripts\python.exe")) {
    Write-Host "Criando .venv ..."
    python -m venv "$Root\.venv"
}
$Py = "$Root\.venv\Scripts\python.exe"
& $Py -m pip install --upgrade pip | Out-Null
& $Py -m pip install -e ".[build]"

$origin = & $Py -c "import exam_trainer, inspect; print(inspect.getfile(exam_trainer))"
$expected = Join-Path $Root "src\exam_trainer"
Write-Host "exam_trainer (.venv): $origin"
if (-not ($origin -like "$expected\*")) {
    Write-Error "exam_trainer nao vem de $expected. Verifique PYTHONPATH e instalacoes antigas."
}

# Diagnostico do Python global (somente leitura).
$globalShow = python -m pip show $Dist 2>$null
$editable = ($globalShow | Select-String -Pattern "Editable project location:").Line
if ($editable -and -not ($editable -like "*$Root*")) {
    Write-Warning "O Python global tem outra copia instalada ($editable)."
    Write-Warning "Se nao for usada, remova com: python -m pip uninstall $Dist"
}
if ("$env:PYTHONPATH" -ne "") {
    Write-Warning "PYTHONPATH esta definido ($env:PYTHONPATH). Ele pode sobrepor a .venv."
}

if ($RunTests) {
    $env:QT_QPA_PLATFORM = "offscreen"
    & $Py -m unittest discover -s tests
}

Write-Host ""
Write-Host "Pronto. Ative o ambiente com:  .\.venv\Scripts\Activate.ps1"
