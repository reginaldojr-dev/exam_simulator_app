#!/usr/bin/env sh
# Prepara o ambiente de desenvolvimento do 42 Exam Trainer (Linux/macOS).
#   ./scripts/dev-setup.sh            # cria .venv e instala
#   ./scripts/dev-setup.sh --run-tests
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$ROOT"
PYTHON=${PYTHON:-python3}

[ -x .venv/bin/python ] || "$PYTHON" -m venv .venv
.venv/bin/python -m pip install --upgrade pip >/dev/null
.venv/bin/python -m pip install -e ".[build]"

ORIGIN=$(.venv/bin/python -c "import exam_trainer, inspect; print(inspect.getfile(exam_trainer))")
echo "exam_trainer (.venv): $ORIGIN"
case "$ORIGIN" in
  "$ROOT/src/exam_trainer/"*) ;;
  *) echo "ERRO: exam_trainer nao vem de $ROOT/src/exam_trainer" >&2; exit 1 ;;
esac
[ -z "${PYTHONPATH:-}" ] || echo "AVISO: PYTHONPATH definido ($PYTHONPATH); pode sobrepor a .venv." >&2

if [ "${1:-}" = "--run-tests" ]; then
  QT_QPA_PLATFORM=offscreen .venv/bin/python -m unittest discover -s tests
fi
echo "Pronto. Ative com: source .venv/bin/activate"
