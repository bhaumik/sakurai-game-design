#!/bin/bash
# Optional acquisition: tools/fetch_videos.sh WORK_DIR [--listing TSV | --refresh] [--profile PATH] [--jobs N]
set -euo pipefail
T=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
D=${1:?work directory required}
shift
exec python3 -I "$T/pipeline_acquire.py" "$D" "$@"
