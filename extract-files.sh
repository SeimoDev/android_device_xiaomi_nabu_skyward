#!/usr/bin/env bash
set -euo pipefail
repo_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
[[ $# -ge 1 ]] || { echo "Usage: $0 ROM.zip [output-directory]" >&2; exit 1; }
python3 "$repo_dir/scripts/extract-rom.py" "$1" --out "${2:-$repo_dir/work/rom}"
