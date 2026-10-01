#!/usr/bin/env sh
# Prepara o ambiente de desenvolvimento do RankedDojo (Linux/macOS).
#   ./scripts/dev-setup.sh            # cria .venv e instala
#   ./scripts/dev-setup.sh --run-tests
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$ROOT"
PYTHON=${PYTHON:-python3}

[ -x .venv/bin/python ] || "$PYTHON" -m venv .venv
.venv/bin/python -m pip install --upgrade pip >/dev/null
.venv/bin/python -m pip install -e ".[build]"

ORIGIN=$(.venv/bin/python -c "import rankeddojo, inspect; print(inspect.getfile(rankeddojo))")
echo "rankeddojo (.venv): $ORIGIN"
case "$ORIGIN" in
  "$ROOT/src/rankeddojo/"*) ;;
  *) echo "ERRO: rankeddojo nao vem de $ROOT/src/rankeddojo" >&2; exit 1 ;;
esac
[ -z "${PYTHONPATH:-}" ] || echo "AVISO: PYTHONPATH definido ($PYTHONPATH); pode sobrepor a .venv." >&2

if [ "${1:-}" = "--run-tests" ]; then
  QT_QPA_PLATFORM=offscreen .venv/bin/python -m unittest discover -s tests
fi
echo "Pronto. Ative com: source .venv/bin/activate"

