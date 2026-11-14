#!/usr/bin/env bash
set -euo pipefail
repo_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
rom_dir=$(realpath "${1:-$repo_dir/work/rom}")
output_dir=${2:-"$repo_dir/out"}
python3 "$repo_dir/bootstrap.py"
bash "$repo_dir/work/skyward/devices/nabu/build.sh" "$rom_dir" "$output_dir"
