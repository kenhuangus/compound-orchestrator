#!/usr/bin/env sh
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
PYTHON=${PYTHON:-python3}

cd "$ROOT"
"$PYTHON" -m unittest discover -s tests -p "test_*.py"
"$PYTHON" scripts/compound_orchestrator.py self-test --root .

if command -v claude >/dev/null 2>&1; then
  claude plugin validate .
  claude --plugin-dir "$ROOT" plugin details compound-orchestrator >/dev/null
fi
