#!/bin/bash
# Optional OCR: tools/run_ocr.sh WORK_DIR PYTHON [--profile PATH] [--rec-model PATH] [--jobs N]
set -euo pipefail
T=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
D=${1:?work directory required}
PY=${2:?Python executable with optional OCR dependencies required}
shift 2
exec "$PY" -I "$T/pipeline_run.py" "$D" --python "$PY" "$@"
