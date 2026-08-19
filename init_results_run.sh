#!/bin/bash
set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
RESULTS_DIR="$SCRIPT_DIR/results"

ordinal_suffix() {
    local n=$1
    local last_two=$((n % 100))
    local last_one=$((n % 10))

    if (( last_two >= 11 && last_two <= 13 )); then
        echo "${n}th"
        return
    fi

    case "$last_one" in
        1) echo "${n}st" ;;
        2) echo "${n}nd" ;;
        3) echo "${n}rd" ;;
        *) echo "${n}th" ;;
    esac
}

next_results_name() {
    local max_index=0
    local entry base number

    mkdir -p "$RESULTS_DIR"

    shopt -s nullglob
    for entry in "$RESULTS_DIR"/*; do
        [ -d "$entry" ] || continue
        base=$(basename "$entry")
        if [[ "$base" =~ ^([0-9]+)(st|nd|rd|th)$ ]]; then
            number=${BASH_REMATCH[1]}
            if (( number > max_index )); then
                max_index=$number
            fi
        fi
    done
    shopt -u nullglob

    ordinal_suffix $((max_index + 1))
}

TARGET_NAME=${1:-$(next_results_name)}
TARGET_DIR="$RESULTS_DIR/$TARGET_NAME"

if [ -e "$TARGET_DIR" ]; then
    echo "Error: $TARGET_DIR already exists." >&2
    echo "Pass a different folder name, or omit the argument to auto-create the next numbered folder." >&2
    exit 1
fi

mkdir -p "$TARGET_DIR"
touch "$TARGET_DIR/node1.txt" "$TARGET_DIR/node2.txt" "$TARGET_DIR/record.txt"

cat <<EOF
Created run folder: $TARGET_DIR

Initialized files:
- node1.txt
- node2.txt
- record.txt

Example:
cd "$TARGET_DIR"
python3 ../../master_final.py --file1 ../../addmult1.bench --file2 ../../addmult2.bench --sub1 "\$(paste -sd, node1.txt)" --sub2 "\$(paste -sd, node2.txt)" --final-cnf final_reduced.cnf --log record.txt
EOF
