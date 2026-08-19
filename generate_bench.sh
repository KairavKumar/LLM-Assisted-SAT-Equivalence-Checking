#!/bin/bash
set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)

if [ -z "$1" ]; then
    echo "Usage: ./generate_bench.sh <path_to_verilog_file> [top_module]"
    exit 1
fi

INPUT_VERILOG=$1
BASENAME=$(basename "$INPUT_VERILOG" .v)
JSON_FILE="${BASENAME}.json"
BENCH_FILE="${BASENAME}.bench"
TOP_MODULE=${2-}

echo "Processing $INPUT_VERILOG..."

if ! command -v yosys >/dev/null 2>&1; then
    echo "Error: yosys not found in PATH. Install yosys or update PATH." >&2
    exit 1
fi

if ! command -v python3 >/dev/null 2>&1; then
    echo "Error: python3 not found in PATH." >&2
    exit 1
fi

# 1. Yosys: Verilog -> JSON (after aigmap)
if [ -z "$TOP_MODULE" ]; then
    yosys -p "
read_verilog $INPUT_VERILOG;
hierarchy -check -auto-top;
proc; opt;
techmap; opt;
flatten; opt;
aigmap; opt_clean;
write_json $JSON_FILE;
" > yosys.log 2>&1
else
    yosys -p "
read_verilog $INPUT_VERILOG;
hierarchy -top $TOP_MODULE;
proc; opt;
techmap; opt;
flatten; opt;
aigmap; opt_clean;
write_json $JSON_FILE;
" > yosys.log 2>&1
fi

# 2. JSON -> BENCH (preserve names) + mapping sidecar
if [ ! -f "$JSON_FILE" ]; then
    echo "Error: JSON output not found: $JSON_FILE" >&2
    echo "Check yosys.log for details." >&2
    exit 1
fi

python3 "$SCRIPT_DIR/yosys_json_to_bench.py" "$JSON_FILE" --output "$BENCH_FILE" > bench.log 2>&1

echo "Generated $BENCH_FILE successfully!"
echo "Mapping written to ${BASENAME}.mapping.json"
